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
from pipelines.video.models import JointTarget, PoseFrame, SequenceVerdict
from pipelines.video.pose import (
    create_landmarker,
    ensure_pose_model,
    extract_all_keypoints,
    reset_person_tracker,
)
from pipelines.video.pose_detector import (
    analyze_all_persons,
    save_fall_evidence,
    save_postural_evidence,
)
from pipelines.video.pose_evaluate import evaluate
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
    "fall_threshold": 0.25,
    "persistence_frames": 1,
    "num_poses": 3,
    "joint_targets": [],
    "trunk_tilt_max": 30.0,
    "tilt_persistence_frames": 90,
    "output_root": "output",
    "model_cache_dir": "models",
}


def _parse_joint_targets(raw: list[dict] | None) -> list[JointTarget]:
    """Converte a lista de dicionários do YAML em ``JointTarget`` validados."""
    if not raw:
        return []
    targets = []
    for entry in raw:
        targets.append(JointTarget(
            joint_name=str(entry["joint_name"]),
            landmark_a=int(entry["landmark_a"]),
            landmark_b=int(entry["landmark_b"]),
            landmark_c=int(entry["landmark_c"]),
            min_angle=float(entry["min_angle"]),
            target_angle=float(entry["target_angle"]),
        ))
    return targets


@dataclass(frozen=True)
class Config:
    dataset_dir: Path
    sequences: list[str] | None
    window_size: int
    fall_threshold: float
    persistence_frames: int
    num_poses: int
    joint_targets: list[JointTarget]
    trunk_tilt_max: float
    tilt_persistence_frames: int
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
    joint_raw = merged.get("joint_targets", [])

    return Config(
        dataset_dir=Path(merged["dataset_dir"]),
        sequences=list(sequences) if sequences else None,
        window_size=int(merged["window_size"]),
        fall_threshold=float(merged["fall_threshold"]),
        persistence_frames=int(merged["persistence_frames"]),
        num_poses=int(merged["num_poses"]),
        joint_targets=_parse_joint_targets(joint_raw),
        trunk_tilt_max=float(merged["trunk_tilt_max"]),
        tilt_persistence_frames=int(merged["tilt_persistence_frames"]),
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


def run(config_path: Path, run_id: str | None = None) -> int:
    """Pipeline unificado: queda + fisioterapia sobre os mesmos frames.

    Extrai keypoints uma vez, roda ambos os detetores em sequência, e gera
    evidência para cada finding encontrado. Mantém retrocompatibilidade com
    o formato URFD.
    """
    cfg = load_config(Path(config_path))
    run_id = run_id or _novo_run_id()
    destino = evidence_dir(_FEATURE, run_id, cfg.output_root)

    seq_dirs = _sequence_dirs(cfg.dataset_dir, cfg.sequences)
    if not seq_dirs:
        log.error("nenhuma sequência utilizável em %s", cfg.dataset_dir)
        return 1

    model_path = ensure_pose_model(cfg.model_cache_dir)
    landmarker = create_landmarker(model_path, num_poses=cfg.num_poses)

    verdicts: list[SequenceVerdict] = []
    n_fall_evidencias = 0
    n_postural_evidencias = 0

    for seq_dir in seq_dirs:
        seq = load_sequence(seq_dir)
        # Reinicia o rastreador de identidade para cada sequência (vídeo distinto)
        reset_person_tracker()

        # Extração multi-pessoa com tracking de identidade persistente
        all_poses = [extract_all_keypoints(p, landmarker) for p in seq.frame_paths]
        from pipelines.video.pose_features import group_poses_by_track_id
        n_pessoas = len(group_poses_by_track_id(all_poses))

        # Pipeline multi-pessoa unificado (ITER2-03)
        _, _, consolidated, _ = analyze_all_persons(
            all_poses_per_frame=all_poses,
            fps=30.0,
            joint_targets=cfg.joint_targets if cfg.joint_targets else None,
            fall_threshold=cfg.fall_threshold,
            persistence_frames=cfg.persistence_frames if n_pessoas <= 1 else 3,
        )

        fall_detected = any(
            c.finding_type == "FALL_DETECTED" for c in consolidated
        )
        verdicts.append(SequenceVerdict(
            seq_id=seq.seq_id,
            predicted="queda" if fall_detected else "adl",
            label=seq.label,
        ))

        # Evidência para cada finding
        for finding in consolidated:
            # Usa o peak_frame (pico de Vy) como frame do evento,
            # e find_pose_by_track_id para garantir que desenhamos
            # a pessoa certa (não a primeira pose do frame).
            event_frame = finding.peak_frame or finding.frame_index
            safe_idx = min(event_frame, len(seq.frame_paths) - 1)
            evidence_pose: PoseFrame | None = None

            if finding.track_id is not None:
                from pipelines.video.pose_features import find_pose_by_track_id
                # Procura no frame exato e nos frames vizinhos (±3)
                for offset in range(0, 4):
                    for direction in (1, -1) if offset > 0 else (1,):
                        search_idx = safe_idx + (offset * direction)
                        if 0 <= search_idx < len(all_poses):
                            evidence_pose = find_pose_by_track_id(
                                all_poses, search_idx, finding.track_id,
                            )
                            if evidence_pose is not None:
                                safe_idx = search_idx
                                break
                    if evidence_pose is not None:
                        break

            if evidence_pose is None:
                # Fallback: primeira pose válida no frame
                if safe_idx < len(all_poses) and all_poses[safe_idx]:
                    for p in all_poses[safe_idx]:
                        if p is not None:
                            evidence_pose = p
                            break

            if evidence_pose is None:
                continue

            if finding.finding_type == "FALL_DETECTED":
                save_fall_evidence(
                    seq_id=seq.seq_id,
                    frame_path=seq.frame_paths[safe_idx],
                    pose_frame=evidence_pose,
                    event_frame_index=safe_idx,
                    score=finding.score,
                    run_id=run_id,
                    root=cfg.output_root,
                    persistence_frames=cfg.persistence_frames,
                    track_id=finding.track_id,
                )
                n_fall_evidencias += 1
            else:
                save_postural_evidence(
                    finding=finding,
                    frame_path=seq.frame_paths[safe_idx],
                    pose_frame=evidence_pose,
                    run_id=run_id,
                    root=cfg.output_root,
                )
                n_postural_evidencias += 1

        n_windows = len(seq.frame_paths) // cfg.window_size
        fall_verdict = "queda" if fall_detected else "adl"
        n_tilt = sum(1 for c in consolidated if c.finding_type == "TRUNK_TILT")
        n_postural = sum(1 for c in consolidated if c.finding_type == "POSTURAL_DEVIATION")
        log.info(
            "%s: %d pessoa(s), %d janelas, %s, %d desvio(s), %d tilt(s)",
            seq.seq_id,
            n_pessoas,
            n_windows,
            fall_verdict,
            n_postural,
            n_tilt,
        )

    destino.mkdir(parents=True, exist_ok=True)
    save_report(evaluate(verdicts), destino / "metrics.json")

    total_evidencias = n_fall_evidencias + n_postural_evidencias
    log.info(
        "run %s: %d sequência(s), %d evidência(s) (%d queda, %d postural) em %s",
        run_id,
        len(seq_dirs),
        total_evidencias,
        n_fall_evidencias,
        n_postural_evidencias,
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
