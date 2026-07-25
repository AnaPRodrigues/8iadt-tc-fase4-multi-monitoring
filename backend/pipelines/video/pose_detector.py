"""Classificação da sequência (queda vs ADL) e evidência do evento.

`classify_sequence` recebe apenas `windows`/`threshold` e devolve o veredito
puro (`"queda" | "adl" | "dados_insuficientes"`); montar o `SequenceVerdict`
completo (juntando `seq_id`/`label` da `Sequence`) é responsabilidade do
chamador -- `pose_detector.py` não tem acesso ao rótulo real da sequência.
"""

from pathlib import Path

import cv2

from common.evidence import Evidence, evidence_dir, save_evidence
from common.logging import get_logger
from pipelines.video.models import JointTarget, MovementWindow, PoseFrame, PosturalFinding

log = get_logger("video.pose_detector")

# Calibrado como ponto de partida contra sequências reais do URFD (mesmo
# princípio de calibração empírica usado em outros limiares do projeto,
# como ABRUPT_CHANGE_THRESHOLD): não é um valor fixado pela
# spec, ajustável ao rodar o pipeline completo sobre o subconjunto curado.
DEFAULT_FALL_THRESHOLD = 0.3
DEFAULT_FALL_THRESHOLD_V2 = 0.55

_MIN_VISIBILITY = 0.5


def classify_sequence(windows: list[MovementWindow], threshold: float) -> str:
    """Classifica a sequência inteira a partir das janelas de movimento.

    "queda" se qualquer janela exceder o limiar de amplitude do centro de
    massa; "adl" se nenhuma exceder; "dados_insuficientes" se não houver
    nenhuma janela (sequência curta demais para uma janela completa)
    -- nunca "adl" por omissão nesse caso.
    """
    if not windows:
        return "dados_insuficientes"
    if any(w.center_of_mass_amplitude > threshold for w in windows):
        return "queda"
    return "adl"


def classify_with_persistence(
    windows: list[MovementWindow], threshold: float, persistence_frames: int,
) -> tuple[str, int | None]:
    """Classifica a sequência com filtro temporal de persistência.

    O alerta de queda só é confirmado se ``persistence_frames`` janelas
    consecutivas excederem o limiar. Se uma janela cair abaixo do limiar antes
    disso, o contador reseta — evita falsos positivos em agachamentos e
    inclinações momentâneas.

    Devolve ``("queda", frame_index)`` com o frame da primeira janela da
    sequência confirmada, ``("adl", None)`` ou ``("dados_insuficientes", None)``.
    """
    if not windows:
        return ("dados_insuficientes", None)

    consecutive = 0
    first_frame: int | None = None

    for w in windows:
        if w.center_of_mass_amplitude > threshold:
            if consecutive == 0:
                first_frame = w.start_frame
            consecutive += 1
            if consecutive >= persistence_frames:
                return ("queda", first_frame)
        else:
            consecutive = 0
            first_frame = None

    return ("adl", None)


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


def detect_postural_deviations(
    frames: list[PoseFrame | None],
    joint_targets: list[JointTarget],
    persistence_frames: int,
    fps: float,
) -> list[PosturalFinding]:
    """Deteta desvios de amplitude articular com persistência temporal.

    Para cada articulação em ``joint_targets``, calcula o ângulo por frame
    (via ``joint_angle``) e conta quantos frames consecutivos ficam abaixo do
    mínimo configurado. Se o contador atingir ``persistence_frames``, emite um
    ``POSTURAL_DEVIATION``. O contador reseta quando o ângulo volta acima do
    mínimo ou é ``None`` (POSE-19).
    """
    from pipelines.video.pose_features import joint_angle as _joint_angle

    findings: list[PosturalFinding] = []
    fps = max(fps, 1.0)

    for jt in joint_targets:
        consecutive = 0
        streak_start: int | None = None

        for idx, frame in enumerate(frames):
            if frame is None:
                consecutive = 0
                streak_start = None
                continue

            angle = _joint_angle(frame, jt.landmark_a, jt.landmark_b, jt.landmark_c)
            if angle is None:
                consecutive = 0
                streak_start = None
                continue

            if angle < jt.min_angle:
                if consecutive == 0:
                    streak_start = idx
                consecutive += 1
                if consecutive >= persistence_frames:
                    score = max(0.0, min(1.0, 1.0 - angle / jt.target_angle))
                    findings.append(PosturalFinding(
                        finding_type="POSTURAL_DEVIATION",
                        joint_name=jt.joint_name,
                        measured_angle=round(angle, 1),
                        expected_angle=jt.min_angle,
                        duration_s=round(consecutive / fps, 1),
                        frame_index=streak_start,
                        score=round(score, 3),
                        description=(
                            f"Amplitude articular reduzida em flexão de {jt.joint_name} "
                            f"(alcançado: {angle:.0f}°, esperado: >{jt.min_angle:.0f}°)."
                        ),
                    ))
                    # Reset para não duplicar achados para a mesma streak
                    consecutive = 0
                    streak_start = None
            else:
                consecutive = 0
                streak_start = None

    return findings


def detect_trunk_tilt(
    frames: list[PoseFrame | None],
    max_angle: float,
    persistence_frames: int,
    fps: float,
) -> list[PosturalFinding]:
    """Deteta inclinação de tronco sustentada com persistência temporal.

    Se a inclinação exceder ``max_angle`` por ``persistence_frames`` frames
    consecutivos, emite um ``TRUNK_TILT``. O contador reseta quando a
    inclinação volta abaixo do limiar ou é ``None`` (POSE-19).
    """
    from pipelines.video.pose_features import trunk_tilt as _trunk_tilt

    findings: list[PosturalFinding] = []
    fps = max(fps, 1.0)
    consecutive = 0
    streak_start: int | None = None

    for idx, frame in enumerate(frames):
        if frame is None:
            consecutive = 0
            streak_start = None
            continue

        angle = _trunk_tilt(frame)
        if angle is None:
            consecutive = 0
            streak_start = None
            continue

        if angle > max_angle:
            if consecutive == 0:
                streak_start = idx
            consecutive += 1
            if consecutive >= persistence_frames:
                score = min(1.0, angle / (2.0 * max_angle))
                findings.append(PosturalFinding(
                    finding_type="TRUNK_TILT",
                    joint_name=None,
                    measured_angle=round(angle, 1),
                    expected_angle=max_angle,
                    duration_s=round(consecutive / fps, 1),
                    frame_index=streak_start,
                    score=round(score, 3),
                    description=(
                        f"Desvio postural / inclinação de tronco sustentada "
                        f"({angle:.0f}° de inclinação por {consecutive / fps:.1f}s)."
                    ),
                ))
                consecutive = 0
                streak_start = None
        else:
            consecutive = 0
            streak_start = None

    return findings


def save_fall_evidence(
    *,
    seq_id: str,
    frame_path: Path,
    pose_frame: PoseFrame,
    event_frame_index: int,
    score: float,
    run_id: str,
    root: str | Path = "output",
    persistence_frames: int = 0,
) -> Evidence:
    """Gera a evidência de queda (frame anotado + metadados) no contrato único de evidência."""
    from pipelines.video.pose_evidence import draw_annotated_frame

    finding = PosturalFinding(
        finding_type="FALL_DETECTED",
        joint_name=None,
        measured_angle=0.0,
        expected_angle=0.0,
        duration_s=0.0,
        frame_index=event_frame_index,
        score=round(float(score), 3),
        description=f"Queda detectada após {persistence_frames} frames consecutivos "
        f"acima do limiar (score {score:.2f}).",
    )

    dest_dir = evidence_dir("video_pose", run_id, root)
    annotated_path = dest_dir / f"{seq_id}-fall.png"
    draw_annotated_frame(frame_path, pose_frame, [finding], annotated_path)

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
        metadata={
            "finding_type": "FALL_DETECTED",
            "seq_id": seq_id,
            "event_frame": event_frame_index,
            "score": round(float(score), 3),
            "persistence_frames": persistence_frames,
            "description": finding.description,
        },
        root=root,
    )


def save_postural_evidence(
    finding: PosturalFinding,
    frame_path: Path,
    pose_frame: PoseFrame,
    run_id: str,
    root: str | Path = "output",
) -> Evidence:
    """Gera evidência para achados de fisioterapia (POSTURAL_DEVIATION, TRUNK_TILT).

    Mesmo contrato de ``save_fall_evidence`` — artefato PNG anotado + sidecar JSON.
    """
    from pipelines.video.pose_evidence import draw_annotated_frame

    source_id = Path(frame_path).stem
    joint_slug = finding.joint_name or "tilt"
    evidence_id = f"{source_id}-{joint_slug}-{finding.measured_angle:.0f}deg"

    dest_dir = evidence_dir("video_pose", run_id, root)
    annotated_path = dest_dir / f"{evidence_id}.png"
    draw_annotated_frame(frame_path, pose_frame, [finding], annotated_path)

    return save_evidence(
        feature="video_pose",
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id=source_id,
        artifact_path=annotated_path,
        metadata={
            "finding_type": finding.finding_type,
            "joint_name": finding.joint_name,
            "measured_angle": finding.measured_angle,
            "expected_angle": finding.expected_angle,
            "duration_s": finding.duration_s,
            "frame_index": finding.frame_index,
            "score": finding.score,
            "description": finding.description,
        },
        root=root,
    )
