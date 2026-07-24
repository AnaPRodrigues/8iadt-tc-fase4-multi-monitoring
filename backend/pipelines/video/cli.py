"""Pipeline ponta a ponta da raia pose (queda) — orquestra `pose_loader` -> `pose.py` ->
`pose_features.py` -> `pose_detector.py`, gravando evidência real via `common.evidence`
e métricas via `pose_evaluate.py` sob ``output/video_pose/<run_id>/``.

Escopo restrito à raia pose (URFD), avaliada em lote contra várias sequências de uma vez.
A raia de estrutura crítica cirúrgica (Endoscapes) opera sobre um quadro único por vez e
é acionada pelo despacho de análise da API (`app/analise.py`), não por este driver de
lote — a métrica de detecção dessa raia (`object_evaluate.py`) é usada pelos testes e
pelo notebook de treino, não por um CLI próprio.

Mesmo esqueleto de `pipelines/vitals/cli.py`/`pipelines/audio/cli.py`:
`run(config_path, run_id)`/`main(argv)`, mesma dica de `make data` em `FileNotFoundError`.
Nenhum módulo pré-existente de `pipelines/video/` é modificado -- só orquestrado aqui.
"""

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from common.evidence import evidence_dir
from common.logging import get_logger
from common.metrics import save_report
from pipelines.video.models import MovementWindow, PoseFrame, SequenceVerdict
from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_keypoints
from pipelines.video.pose_detector import (
    DEFAULT_FALL_THRESHOLD,
    classify_sequence,
    save_fall_evidence,
)
from pipelines.video.pose_evaluate import evaluate
from pipelines.video.pose_features import windowed_features
from pipelines.video.pose_loader import load_sequence

log = get_logger("video.cli")

_FEATURE = "video_pose"

# Config própria deste driver (padrão de validação de `pipelines/audio/config.py`:
# campo desconhecido = erro). `sequences=None` processa todo o dataset; uma lista
# explícita restringe a um subconjunto (útil para manter os testes de integração rápidos).
# `window_size=30` calibrado empiricamente contra sequências reais do URFD (mesmo
# princípio de calibração de DEFAULT_FALL_THRESHOLD em `pose_detector.py`): é o menor
# tamanho de janela que separa `fall-01`/`adl-01` reais sob o limiar default.
DEFAULTS: dict[str, Any] = {
    "sequences": None,
    "window_size": 30,
    "fall_threshold": DEFAULT_FALL_THRESHOLD,
    "output_root": "output",
    "model_cache_dir": "models",
}


@dataclass(frozen=True)
class Config:
    dataset_dir: Path
    sequences: list[str] | None
    window_size: int
    fall_threshold: float
    output_root: Path
    model_cache_dir: Path


def load_config(path: Path) -> Config:
    """Lê e valida a config, aplicando os defaults documentados em `DEFAULTS`."""
    if not Path(path).is_file():
        raise FileNotFoundError(f"config inexistente: {path}")

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config precisa ser um mapa de chave/valor")

    known = {"dataset_dir"} | set(DEFAULTS)
    for key in raw:
        if key not in known:
            raise ValueError(f"campo desconhecido na config: {key}")
    if "dataset_dir" not in raw:
        raise ValueError("campo obrigatório ausente na config: dataset_dir")

    merged = {**DEFAULTS, **raw}
    sequences = merged["sequences"]

    return Config(
        dataset_dir=Path(merged["dataset_dir"]),
        sequences=list(sequences) if sequences else None,
        window_size=int(merged["window_size"]),
        fall_threshold=float(merged["fall_threshold"]),
        output_root=Path(merged["output_root"]),
        model_cache_dir=Path(merged["model_cache_dir"]),
    )


def _novo_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _sequence_dirs(dataset_dir: Path, sequences: list[str] | None) -> list[Path]:
    if sequences:
        return [dataset_dir / seq_id for seq_id in sequences]
    return sorted(
        p
        for p in dataset_dir.iterdir()
        if p.is_dir() and (p.name.startswith("fall-") or p.name.startswith("adl-"))
    )


def _representative_frame_index(window: MovementWindow, frames: list[PoseFrame | None]) -> int:
    """Primeiro frame com pose detectada dentro da janela que disparou a queda --
    `windowed_features` garante que ao menos um exista (janela sem frame válido não é gerada)."""
    for idx in range(window.start_frame, window.end_frame + 1):
        if frames[idx] is not None:
            return idx
    raise ValueError("janela sem nenhum frame com pose detectada")


def run(config_path: Path, run_id: str | None = None) -> int:
    """Executa a raia pose ponta a ponta. Devolve 0 em sucesso, 1 quando não há
    sequência utilizável no dataset configurado."""
    cfg = load_config(Path(config_path))
    run_id = run_id or _novo_run_id()
    destino = evidence_dir(_FEATURE, run_id, cfg.output_root)

    seq_dirs = _sequence_dirs(cfg.dataset_dir, cfg.sequences)
    if not seq_dirs:
        log.error("nenhuma sequência utilizável em %s", cfg.dataset_dir)
        return 1

    model_path = ensure_pose_model(cfg.model_cache_dir)
    landmarker = create_landmarker(model_path)

    verdicts: list[SequenceVerdict] = []
    n_evidencias = 0

    for seq_dir in seq_dirs:
        seq = load_sequence(seq_dir)
        frames = [extract_keypoints(p, landmarker) for p in seq.frame_paths]
        windows = windowed_features(frames, cfg.window_size)
        predicted = classify_sequence(windows, cfg.fall_threshold)
        verdicts.append(SequenceVerdict(seq_id=seq.seq_id, predicted=predicted, label=seq.label))

        if predicted == "queda":
            evento = next(w for w in windows if w.center_of_mass_amplitude > cfg.fall_threshold)
            idx = _representative_frame_index(evento, frames)
            save_fall_evidence(
                seq_id=seq.seq_id,
                frame_path=seq.frame_paths[idx],
                pose_frame=frames[idx],
                event_frame_index=idx,
                score=evento.center_of_mass_amplitude,
                run_id=run_id,
                root=cfg.output_root,
            )
            n_evidencias += 1

    destino.mkdir(parents=True, exist_ok=True)
    save_report(evaluate(verdicts), destino / "metrics.json")

    log.info(
        "run %s: %d sequência(s), %d evidência(s) em %s",
        run_id,
        len(seq_dirs),
        n_evidencias,
        destino,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline da raia pose (queda) de vídeo")
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
