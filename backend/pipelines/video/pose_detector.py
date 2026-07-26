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

    Para cada articulação, emite **um único finding por streak contínua**
    (não um por frame). O finding regista o pior ângulo (mínimo) e a duração
    total da streak. O contador só reseta quando o ângulo recupera acima do
    mínimo ou é ``None``.
    """
    from pipelines.video.pose_features import joint_angle as _joint_angle

    findings: list[PosturalFinding] = []
    fps = max(fps, 1.0)

    for jt in joint_targets:
        consecutive = 0
        streak_start: int | None = None
        worst_angle: float = float("inf")
        emitted = False  # evita duplicar o mesmo finding

        for idx, frame in enumerate(frames):
            if frame is None:
                consecutive = 0
                streak_start = None
                worst_angle = float("inf")
                emitted = False
                continue

            angle = _joint_angle(frame, jt.landmark_a, jt.landmark_b, jt.landmark_c)
            if angle is None:
                consecutive = 0
                streak_start = None
                worst_angle = float("inf")
                emitted = False
                continue

            if angle < jt.min_angle:
                if consecutive == 0:
                    streak_start = idx
                    worst_angle = angle
                consecutive += 1
                worst_angle = min(worst_angle, angle)
                if consecutive >= persistence_frames and not emitted:
                    score = max(0.0, min(1.0, 1.0 - worst_angle / jt.target_angle))
                    findings.append(PosturalFinding(
                        finding_type="POSTURAL_DEVIATION",
                        joint_name=jt.joint_name,
                        measured_angle=round(worst_angle, 1),
                        expected_angle=jt.min_angle,
                        duration_s=round(consecutive / fps, 1),
                        frame_index=streak_start,
                        score=round(score, 3),
                        description=(
                            f"Amplitude articular reduzida em flexão de {jt.joint_name} "
                            f"(menor ângulo: {worst_angle:.0f}°, esperado: >{jt.min_angle:.0f}°"
                            f", {consecutive} quadros)."
                        ),
                    ))
                    emitted = True
            else:
                consecutive = 0
                streak_start = None
                worst_angle = float("inf")
                emitted = False

    return findings


def detect_trunk_tilt(
    frames: list[PoseFrame | None],
    max_angle: float,
    persistence_frames: int,
    fps: float,
) -> list[PosturalFinding]:
    """Deteta inclinação de tronco sustentada com persistência temporal.

    Emite **um único finding por streak contínua** com o pior ângulo (máximo)
    e a duração total. O contador só reseta quando a inclinação recupera.
    """
    from pipelines.video.pose_features import trunk_tilt as _trunk_tilt

    findings: list[PosturalFinding] = []
    fps = max(fps, 1.0)
    consecutive = 0
    streak_start: int | None = None
    worst_angle: float = 0.0
    emitted = False

    for idx, frame in enumerate(frames):
        if frame is None:
            consecutive = 0
            streak_start = None
            worst_angle = 0.0
            emitted = False
            continue

        angle = _trunk_tilt(frame)
        if angle is None:
            consecutive = 0
            streak_start = None
            worst_angle = 0.0
            emitted = False
            continue

        if angle > max_angle:
            if consecutive == 0:
                streak_start = idx
                worst_angle = angle
            consecutive += 1
            worst_angle = max(worst_angle, angle)
            if consecutive >= persistence_frames and not emitted:
                score = min(1.0, worst_angle / (2.0 * max_angle))
                findings.append(PosturalFinding(
                    finding_type="TRUNK_TILT",
                    joint_name=None,
                    measured_angle=round(worst_angle, 1),
                    expected_angle=max_angle,
                    duration_s=round(consecutive / fps, 1),
                    frame_index=streak_start,
                    score=round(score, 3),
                    description=(
                        f"Desvio postural / inclinação de tronco sustentada "
                        f"({worst_angle:.0f}° de inclinação por {consecutive / fps:.1f}s)."
                    ),
                ))
                emitted = True
        else:
            consecutive = 0
            streak_start = None
            worst_angle = 0.0
            emitted = False

    return findings


# --------------------------------------------------------------------------- #
# Sumarização de achados — agrupa findings repetidos por articulação/tipo
# --------------------------------------------------------------------------- #
_TRADUCAO_ARTICULACAO = {
    "knee_left": "joelho esquerdo",
    "knee_right": "joelho direito",
    "elbow_left": "cotovelo esquerdo",
    "elbow_right": "cotovelo direito",
}


def validate_fall_dynamic(
    fall_verdict: str,
    fall_frame_idx: int | None,
    velocities: list[float | None],
    min_vertical_velocity: float = 0.10,
    all_poses_per_frame: list[list[PoseFrame | None]] | None = None,
) -> tuple[str, int | None, float, str, int, int | None]:
    """Validação dinâmica de queda multi-pessoa com fallback para oclusão.

    Itera sobre **todas** as poses detetadas no frame. Se qualquer pessoa
    satisfizer as condições de queda, o evento é registado.

    Devolve ``(verdict, frame_idx, velocity_score, description, person_index, peak_vy_frame)``.
    """
    if fall_verdict != "queda":
        return (fall_verdict, fall_frame_idx, 0.0, "", -1, None)

    from pipelines.video.pose_features import (
        lateral_displacement,
        max_vertical_velocity,
        trunk_tilt,
        vertical_velocity_robust,
    )

    best_vy = 0.0
    best_description = ""
    best_person = -1
    best_peak_frame: int | None = None
    _MIN_TILT_FOR_FALL = 25.0

    all_vy: list[list[float | None]] = [velocities]
    all_person_frames: list[list[PoseFrame | None]] = []

    if all_poses_per_frame:
        max_people = max((len(p) for p in all_poses_per_frame if p), default=0)
        if max_people > 1:
            all_vy = []
            for p_idx in range(max_people):
                pf: list[PoseFrame | None] = [
                    poses[p_idx] if poses and p_idx < len(poses) else None
                    for poses in all_poses_per_frame
                ]
                all_person_frames.append(pf)
                all_vy.append(vertical_velocity_robust(pf))
        else:
            all_person_frames = [all_poses_per_frame[0] if all_poses_per_frame else []]
    else:
        all_person_frames = [[]]

    for p_idx, vy_list in enumerate(all_vy):
        person_frames = all_person_frames[p_idx] if p_idx < len(all_person_frames) else []

        tilts = [t for f in person_frames if f is not None for t in [trunk_tilt(f)] if t is not None]
        max_tilt = max(tilts) if tilts else 0.0

        max_vy = max_vertical_velocity(vy_list)

        if max_vy >= min_vertical_velocity and max_tilt >= _MIN_TILT_FOR_FALL:
            if max_vy > best_vy:
                best_vy = max_vy
                best_person = p_idx
                # Frame do pico de Vy (onde a velocidade é máxima)
                valid_vy = [(i, v) for i, v in enumerate(vy_list) if v is not None]
                if valid_vy:
                    best_peak_frame = max(valid_vy, key=lambda x: x[1])[0]
                best_description = (
                    f"Queda abrupta detectada no frame {best_peak_frame} "
                    f"(variação de velocidade vertical Vy = {max_vy:.3f}/frame, "
                    f"inclinação do tronco = {max_tilt:.0f}°)."
                )
            continue

        dx_list = lateral_displacement(person_frames)
        valid_dx = [v for v in dx_list if v is not None]
        max_dx = max(valid_dx) if len(valid_dx) >= 5 else 0.0

        if max_dx > 0.05 and max_vy > 0.05:
            combined = (max_dx + max_vy) / 2.0
            if combined > best_vy:
                best_vy = combined
                best_person = p_idx
                valid_vy = [(i, v) for i, v in enumerate(vy_list) if v is not None]
                best_peak_frame = max(valid_vy, key=lambda x: x[1])[0] if valid_vy else None
                best_description = (
                    f"Queda por rolamento/escorregamento detectada "
                    f"(deslocamento lateral ΔX = {max_dx:.3f}, Vy = {max_vy:.3f})."
                )

    if best_vy < min_vertical_velocity:
        return (
            "adl", None, round(best_vy, 3),
            "Postura reclinada/estática detectada — sem evidência de queda "
            f"(Vy max = {best_vy:.3f}/frame, abaixo do limiar {min_vertical_velocity}).",
            -1, None,
        )

    return ("queda", fall_frame_idx, round(best_vy, 3), best_description, best_person, best_peak_frame)


def sumarizar_achados_video(
    postural_findings: list[PosturalFinding],
    tilt_findings: list[PosturalFinding],
    fall_detected: bool,
) -> tuple[str, float, list[PosturalFinding]]:
    """Consolida findings repetidos em descrições agrupadas e pontuação única.

    Devolve ``(resumo, pontuacao, consolidated)`` onde *consolidated* contém
    no máximo 1 finding por articulação + 1 por tilt + 1 por queda.
    """
    partes: list[str] = []
    consolidated: list[PosturalFinding] = []
    pontuacao = 0.0

    # --- Queda ---
    if fall_detected:
        partes.append("Queda detectada")
        pontuacao = max(pontuacao, 0.80)

    # --- Desvios posturais: agrupa por articulação ---
    por_articulacao: dict[str, list[PosturalFinding]] = {}
    for f in postural_findings:
        key = f.joint_name or "desconhecido"
        por_articulacao.setdefault(key, []).append(f)

    for joint_name, findings in por_articulacao.items():
        if not findings:
            continue
        nome_pt = _TRADUCAO_ARTICULACAO.get(joint_name, joint_name)
        pior = min(findings, key=lambda f: f.measured_angle)
        n_quadros = sum(f.duration_s * 30 for f in findings)  # ~30 fps
        n_quadros = max(int(n_quadros), 1)

        partes.append(
            f"Flexão de {nome_pt} limitada "
            f"(menor ângulo: {pior.measured_angle:.0f}°, "
            f"esperado: >{pior.expected_angle:.0f}°) "
            f"detectada em {n_quadros} quadros."
        )
        # Finding consolidado com o pior ângulo
        consolidated.append(PosturalFinding(
            finding_type="POSTURAL_DEVIATION",
            joint_name=joint_name,
            measured_angle=pior.measured_angle,
            expected_angle=pior.expected_angle,
            duration_s=sum(f.duration_s for f in findings),
            frame_index=pior.frame_index,
            score=pior.score,
            description=partes[-1],
        ))
        pontuacao = max(pontuacao, pior.score)

    # --- Tilt: consolida num único achado ---
    if tilt_findings:
        pior_tilt = max(tilt_findings, key=lambda f: f.measured_angle)
        duracao_total = sum(f.duration_s for f in tilt_findings)
        partes.append(
            "Desvio postural / inclinação de tronco sustentada "
            "detectada durante o exercício."
        )
        consolidated.append(PosturalFinding(
            finding_type="TRUNK_TILT",
            joint_name=None,
            measured_angle=pior_tilt.measured_angle,
            expected_angle=pior_tilt.expected_angle,
            duration_s=duracao_total,
            frame_index=pior_tilt.frame_index,
            score=pior_tilt.score,
            description=partes[-1],
        ))
        pontuacao = max(pontuacao, pior_tilt.score)

    resumo = " | ".join(partes) + "." if partes else "Sem alterações detectadas."
    return resumo, round(pontuacao, 3), consolidated


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
