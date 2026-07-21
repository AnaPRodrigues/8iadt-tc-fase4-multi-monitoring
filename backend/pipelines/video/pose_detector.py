"""Classificação da sequência (queda vs ADL) e evidência do evento (VIDEO-03, VIDEO-05, VIDEO-14).

SPEC_DEVIATION: o design assina `classify_sequence(...) -> SequenceVerdict`, mas
`SequenceVerdict` carrega `seq_id`/`label` que não são entradas desta função
(ela só recebe `windows`/`threshold`, per `tasks.md` T4). Devolve o veredito
puro (`"queda" | "adl" | "dados_insuficientes"`); montar o `SequenceVerdict`
completo (juntando `seq_id`/`label` da `Sequence`) é responsabilidade do
chamador -- `pose_detector.py` não tem acesso ao rótulo real da sequência.
"""

from pathlib import Path

import cv2

from common.evidence import Evidence, evidence_dir, save_evidence
from common.logging import get_logger
from pipelines.video.models import MovementWindow, PoseFrame

log = get_logger("video.pose_detector")

# Calibrado como ponto de partida contra sequências reais do URFD (mesmo
# princípio de ABRUPT_CHANGE_THRESHOLD em F3): não é um valor fixado pela
# spec, ajustável ao rodar o pipeline completo sobre o subconjunto curado.
DEFAULT_FALL_THRESHOLD = 0.3

_MIN_VISIBILITY = 0.5


def classify_sequence(windows: list[MovementWindow], threshold: float) -> str:
    """Classifica a sequência inteira a partir das janelas de movimento.

    "queda" se qualquer janela exceder o limiar de amplitude do centro de
    massa; "adl" se nenhuma exceder; "dados_insuficientes" se não houver
    nenhuma janela (sequência curta demais para uma janela completa,
    VIDEO-14) -- nunca "adl" por omissão nesse caso.
    """
    if not windows:
        return "dados_insuficientes"
    if any(w.center_of_mass_amplitude > threshold for w in windows):
        return "queda"
    return "adl"


def draw_keypoints(frame_path: Path, pose_frame: PoseFrame, output_path: Path) -> Path:
    """Desenha os landmarks com visibilidade suficiente sobre o frame real."""
    image = cv2.imread(str(frame_path))
    if image is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")

    height, width = image.shape[:2]
    for x, y, _z, visibility in pose_frame.landmarks:
        if visibility < _MIN_VISIBILITY:
            continue
        cv2.circle(image, (int(x * width), int(y * height)), 4, (0, 0, 255), -1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path


def save_fall_evidence(
    *,
    seq_id: str,
    frame_path: Path,
    pose_frame: PoseFrame,
    event_frame_index: int,
    score: float,
    run_id: str,
    root: str | Path = "output",
) -> Evidence:
    """Gera a evidência de queda (frame anotado + metadados) no contrato único (AD-026)."""
    dest_dir = evidence_dir("video_pose", run_id, root)
    annotated_path = dest_dir / f"{seq_id}-fall.png"
    draw_keypoints(frame_path, pose_frame, annotated_path)

    log.info(
        "queda detectada na sequência %s (frame %d, score=%.4f)",
        seq_id,
        event_frame_index,
        score,
    )

    return save_evidence(
        feature="video_pose",
        run_id=run_id,
        evidence_id=f"{seq_id}-fall",
        source_record_id=seq_id,
        artifact_path=annotated_path,
        metadata={"seq_id": seq_id, "event_frame": event_frame_index, "score": score},
        root=root,
    )
