"""Pipeline ponta a ponta de F2 — orquestra P1 (ICBHI) + P2 (transcrição/termos/sentimento) +
P3 (fadiga vocal), gravando tudo sob ``output/audio/<run_id>/``.

Mesmo esqueleto de ``pipelines/vitals/cli.py``: ``run(config_path, run_id)``/``main(argv)``,
mesma dica de ``make data`` em ``FileNotFoundError``.
"""

import argparse
import dataclasses
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from common.evidence import evidence_dir, save_evidence
from common.logging import get_logger
from pipelines.audio.acoustic_features import extract as extract_acoustic_features
from pipelines.audio.config import Config, load_config
from pipelines.audio.critical_terms import find_terms, load_terms, save_term_evidence
from pipelines.audio.fatigue_score import is_fatigued
from pipelines.audio.fatigue_score import score as fatigue_score
from pipelines.audio.icbhi_classifier import predict, split_by_patient, train
from pipelines.audio.icbhi_evaluate import evaluate, save_evaluation
from pipelines.audio.icbhi_evidence import save_cycle_evidence
from pipelines.audio.icbhi_loader import load_dataset, select_subset
from pipelines.audio.models import AcousticFeatures, RespiratoryCycle, Transcript
from pipelines.audio.sentiment import classify as classify_sentiment
from pipelines.audio.transcribe import transcribe

log = get_logger("audio.cli")

_CLASSES = ("normal", "crackle", "wheeze", "both")
_FEATURE = "audio"

# Fração reservada para teste no split por paciente do ICBHI: decisão local da CLI
# (não faz parte da config declarativa, mesmo princípio de MAX_GAP_S em vitals/cli.py).
_TEST_SIZE = 0.3


def _novo_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _run_p1(cfg: Config, run_id: str, destino: Path) -> int:
    """ICBHI: carrega, treina, avalia e grava evidência de ciclo anômalo.

    Devolve o nº de evidências geradas.
    """
    cycles, falhas = load_dataset(cfg.icbhi_dataset_dir)

    cycles_by_patient: dict[str, list[RespiratoryCycle]] = {}
    for cycle in cycles:
        cycles_by_patient.setdefault(cycle.patient_id, []).append(cycle)

    subset = select_subset(cycles_by_patient, cfg.icbhi_max_patients, cfg.seed)
    if not subset:
        log.error(
            "nenhum ciclo utilizável em %s (%d arquivo(s) descartado(s))",
            cfg.icbhi_dataset_dir,
            len(falhas),
        )
        return -1

    train_cycles, test_cycles = split_by_patient(subset, test_size=_TEST_SIZE, seed=cfg.seed)
    model = train(train_cycles, seed=cfg.seed)
    predictions = [predict(model, cycle) for cycle in test_cycles]

    y_true = [cycle.label for cycle in test_cycles]
    y_pred = [pred.predicted_label for pred in predictions]
    reports = evaluate(y_true, y_pred, _CLASSES)
    save_evaluation(reports, destino / "metrics.json")

    n_evidencias = 0
    for cycle, pred in zip(test_cycles, predictions, strict=True):
        if save_cycle_evidence(cycle, pred, run_id, cfg.output_root) is not None:
            n_evidencias += 1

    log.info(
        "P1: %d ciclo(s) de treino, %d de teste, %d evidência(s), %d arquivo(s) descartado(s)",
        len(train_cycles),
        len(test_cycles),
        n_evidencias,
        len(falhas),
    )
    return n_evidencias


@dataclasses.dataclass
class _ConsultResult:
    audio_path: Path
    transcript: Transcript
    features: AcousticFeatures | None


def _processa_p2(cfg: Config, run_id: str, transcript: Transcript) -> tuple[str | None, float, int]:
    """Termos críticos + sentimento; pulado quando o transcript não é confiável (AUDIO-10)."""
    if not transcript.reliable:
        log.warning("transcrição não confiável para %s: termos críticos/sentimento pulados",
                    transcript.audio_path)
        return None, 0.0, 0

    terms = load_terms(cfg.critical_terms_path)
    hits = find_terms(transcript, terms)
    for hit in hits:
        save_term_evidence(hit, transcript, run_id, cfg.output_root)

    sentimento = classify_sentiment(transcript.text, cfg.sentiment_threshold)
    return sentimento.label, sentimento.score, len(hits)


def _salva_evidencia_fadiga(
    resultado: _ConsultResult, fadiga: float, run_id: str, output_root, destino: Path
) -> None:
    stem = resultado.audio_path.stem
    evidence_id = f"{stem}-fatigue"
    artifact_path = destino / f"{evidence_id}.txt"
    artifact_path.write_text(
        f"possível fadiga vocal (heurística não validada clinicamente)\n"
        f"audio: {resultado.audio_path}\nscore: {fadiga:.3f}\n"
        f"features: {dataclasses.asdict(resultado.features)}\n",
        encoding="utf-8",
    )
    save_evidence(
        feature=_FEATURE,
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id=stem,
        artifact_path=artifact_path,
        metadata={"fatigue_score": fadiga, **dataclasses.asdict(resultado.features)},
        root=output_root,
    )


def _run_p2_p3(cfg: Config, run_id: str, destino: Path) -> None:
    """Transcreve cada áudio de consulta e roda P2 (termos/sentimento) + P3 (fadiga vocal)."""
    if not cfg.consult_audio_paths:
        log.warning("consult_audio_paths vazio: pulando P2/P3")
        return

    resultados: list[_ConsultResult] = []
    resumos: dict[Path, dict] = {}

    for audio_path in cfg.consult_audio_paths:
        try:
            transcript = transcribe(audio_path, cfg.whisper_model_size, cfg.no_speech_threshold)
        except Exception as exc:  # áudio corrompido/formato não suportado (AUDIO-12)
            log.warning("falha ao processar áudio de consulta %s: %s", audio_path, exc)
            continue

        sentiment_label, sentiment_score, n_termos = _processa_p2(cfg, run_id, transcript)
        resumos[audio_path] = {
            "audio_path": str(audio_path),
            "reliable": transcript.reliable,
            "sentiment_label": sentiment_label,
            "sentiment_score": sentiment_score,
            "critical_terms_found": n_termos,
        }

        try:
            features = extract_acoustic_features(audio_path, transcript)
        except Exception as exc:
            log.warning("falha ao extrair features acústicas de %s: %s", audio_path, exc)
            features = None

        resultados.append(
            _ConsultResult(audio_path=audio_path, transcript=transcript, features=features)
        )

    baseline = [r.features for r in resultados if r.features is not None]

    for resultado in resultados:
        resumo = resumos[resultado.audio_path]
        if resultado.features is not None and baseline:
            fadiga = fatigue_score(resultado.features, baseline)
            fatigado = is_fatigued(fadiga, cfg.fatigue_threshold)
            resumo["fatigue_score"] = fadiga
            resumo["fatigued"] = fatigado
            if fatigado:
                _salva_evidencia_fadiga(resultado, fadiga, run_id, cfg.output_root, destino)
        else:
            resumo["fatigue_score"] = None
            resumo["fatigued"] = None

        stem = resultado.audio_path.stem
        (destino / f"{stem}-summary.json").write_text(
            json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    log.info("P2/P3: %d áudio(s) de consulta processado(s)", len(resultados))


def run(config_path: Path, run_id: str | None = None) -> int:
    """Executa o pipeline. Devolve 0 em sucesso, 1 quando o ICBHI não tem o que processar."""
    cfg = load_config(Path(config_path))
    run_id = run_id or _novo_run_id()
    destino = evidence_dir(_FEATURE, run_id, cfg.output_root)
    destino.mkdir(parents=True, exist_ok=True)

    n_evidencias_p1 = _run_p1(cfg, run_id, destino)
    if n_evidencias_p1 < 0:
        return 1

    _run_p2_p3(cfg, run_id, destino)

    log.info("run %s completo em %s", run_id, destino)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de análise de áudio (F2)")
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
