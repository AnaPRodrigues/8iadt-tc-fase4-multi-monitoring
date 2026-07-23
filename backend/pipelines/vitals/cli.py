"""Pipeline ponta a ponta de monitoramento de sinais vitais — o que ``make demo`` executa.

Encadeia: carga → preprocess → janelamento → features → detectores → agregação →
avaliação, gravando métricas e evidências sob ``output/vitals/<run_id>/``.
"""

import argparse
import dataclasses
import sys
from datetime import UTC, datetime
from pathlib import Path

from common.config import Config, load_config
from common.evidence import evidence_dir, save_evidence
from common.logging import get_logger
from pipelines.vitals.aggregate import RecordVerdict, aggregate
from pipelines.vitals.compositor import TimelineSpec, compose
from pipelines.vitals.detectors import AnomalyEvent, IsolationForestDetector, RollingZScoreDetector
from pipelines.vitals.evaluate import evaluate, save_evaluation
from pipelines.vitals.features import extract
from pipelines.vitals.loader import VitalRecord, load_dataset
from pipelines.vitals.plot import plot_anomaly_window
from pipelines.vitals.preprocess import interpolate_gaps, mark_signal_loss
from pipelines.vitals.windowing import make_windows

log = get_logger("vitals.cli")

# Gaps de até 5 s são curtos o bastante para interpolar sem inventar fisiologia;
# acima disso o trecho fica marcado como inválido.
MAX_GAP_S = 5.0


def _novo_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _limpa(record: VitalRecord):
    """Marca perda de sinal no FHR e interpola gaps curtos."""
    mask = mark_signal_loss(record.fhr)
    fhr, mask = interpolate_gaps(record.fhr, mask, max_gap_s=MAX_GAP_S, fs=record.fs)
    return dataclasses.replace(record, fhr=fhr), mask


def _proveniencia(record: VitalRecord, start_s: float) -> str:
    """Registro real de onde o trecho veio (relevante na timeline composta)."""
    idx = int(start_s * record.fs)
    for seg in record.provenance:
        if seg.start_idx <= idx < seg.end_idx:
            return seg.source_record_id
    return record.record_id


def build_event(record: VitalRecord, detector_name: str, janela, score: float) -> AnomalyEvent:
    """Monta o evento de anomalia preservando fielmente detector, score e janela."""
    return AnomalyEvent(
        record_id=record.record_id,
        detector=detector_name,
        start_s=janela.start_s,
        end_s=janela.end_s,
        score=float(score),
        source_record_id=_proveniencia(record, janela.start_s),
    )


def evidence_id_de(evento: AnomalyEvent) -> str:
    """Identificador da evidência, derivado do próprio evento.

    Derivar do evento (em vez de montar em paralelo) garante que o nome do arquivo e
    os metadados nunca divirjam sobre qual detector produziu a anomalia.
    """
    return f"{evento.record_id}-{evento.detector}-{evento.start_s:.0f}s"


def run(config_path: Path, run_id: str | None = None) -> int:
    """Executa o pipeline. Devolve 0 em sucesso, 1 quando não há o que processar."""
    cfg: Config = load_config(Path(config_path))
    run_id = run_id or _novo_run_id()
    destino = evidence_dir("vitals", run_id, cfg.output_root)

    if cfg.timeline:
        registros = [
            compose(TimelineSpec(dataset_dir=cfg.dataset_dir, record_ids=cfg.timeline))
        ]
        falhas = []
        log.info("timeline composta a partir de: %s", ", ".join(cfg.timeline))
    else:
        registros, falhas = load_dataset(cfg.dataset_dir)

    if not registros:
        log.error(
            "nenhum registro utilizável em %s (%d descartado(s))", cfg.dataset_dir, len(falhas)
        )
        return 1

    detectores = [
        RollingZScoreDetector(threshold=cfg.zscore_threshold),
        IsolationForestDetector(contamination=cfg.iforest_contamination, seed=cfg.seed),
    ]

    verdicts: dict[str, list[RecordVerdict]] = {d.name: [] for d in detectores}
    n_evidencias = 0

    for record in registros:
        limpo, mask = _limpa(record)
        janelas = make_windows(limpo, cfg.window_size_s, cfg.window_stride_s, mask)
        if not janelas:
            log.warning("registro %s é curto demais para uma janela", record.record_id)
        features = [extract(j, fs=limpo.fs) for j in janelas]

        for detector in detectores:
            scores = detector.score(features)
            flags = detector.flag(features)
            verdicts[detector.name].append(aggregate(record.record_id, flags, cfg.tau))

            for janela, flag, score in zip(janelas, flags, scores, strict=True):
                if not flag:
                    continue
                evento = build_event(limpo, detector.name, janela, score)
                evidence_id = evidence_id_de(evento)
                destino.mkdir(parents=True, exist_ok=True)
                artefato = plot_anomaly_window(limpo, evento, destino / f"{evidence_id}.png")
                save_evidence(
                    feature="vitals",
                    run_id=run_id,
                    evidence_id=evidence_id,
                    source_record_id=evento.source_record_id,
                    artifact_path=artefato,
                    metadata=dataclasses.asdict(evento) | {"ph": record.ph},
                    root=cfg.output_root,
                )
                n_evidencias += 1

    relatorio = evaluate(verdicts, registros)
    save_evaluation(relatorio, destino / "metrics.json")

    log.info(
        "run %s: %d registro(s), %d descartado(s), %d evidência(s) em %s",
        run_id,
        len(registros),
        len(falhas),
        n_evidencias,
        destino,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de detecção de anomalias em CTG")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    try:
        return run(args.config, args.run_id)
    except FileNotFoundError as exc:
        log.error(
            "%s\nBaixe os datasets antes de rodar a demo:\n  make data",
            exc,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
