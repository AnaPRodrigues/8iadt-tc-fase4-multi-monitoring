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
DEFAULT_FALL_THRESHOLD_V2 = 0.25

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
# Detector de convulsão/espasmo — oscilação multi-articular (ITER2-04)
# --------------------------------------------------------------------------- #
def detect_seizure(
    frames: list[PoseFrame | None],
    fps: float,
    window_frames: int = 60,
    min_std: float = 0.05,
    persistence_frames: int = 30,
) -> list[PosturalFinding]:
    """Deteta convulsão/espasmo via oscilação rítmica multi-articular.

    Calcula a velocidade angular (variação frame a frame) de 4 articulações
    — cotovelo E (11-13-15), cotovelo D (12-14-16), joelho E (23-25-27),
    joelho D (24-26-28) — e mede o desvio padrão numa janela deslizante.
    Se o std médio das articulações exceder ``min_std`` por
    ``persistence_frames`` consecutivos, emite um finding "SEIZURE".

    Articulações com visibilidade < 0.4 são excluídas do frame sem
    invalidar a janela.
    """
    from pipelines.video.pose_features import joint_angle as _joint_angle

    _JOINT_TRIPLETS = [
        (11, 13, 15),  # cotovelo esquerdo
        (12, 14, 16),  # cotovelo direito
        (23, 25, 27),  # joelho esquerdo
        (24, 26, 28),  # joelho direito
    ]

    if len(frames) < window_frames:
        return []

    # Pré-calcula ângulos: [joint][frame] = angle | None
    angles: list[list[float | None]] = [[] for _ in _JOINT_TRIPLETS]
    for frame in frames:
        if frame is None:
            for j in range(len(_JOINT_TRIPLETS)):
                angles[j].append(None)
            continue
        for j, (a, b, c) in enumerate(_JOINT_TRIPLETS):
            angles[j].append(_joint_angle(frame, a, b, c))

    n = len(frames)
    # std deslizante por articulação
    std_windows: list[float] = []
    for i in range(window_frames - 1, n):
        joint_stds: list[float] = []
        for j in range(len(_JOINT_TRIPLETS)):
            # Velocidades angulares nesta janela
            window = angles[j][i - window_frames + 1 : i + 1]
            velocities = []
            for k in range(1, len(window)):
                prev_a = window[k - 1]
                curr_a = window[k]
                if prev_a is not None and curr_a is not None:
                    velocities.append(abs(curr_a - prev_a))
            if velocities:
                # Desvio padrão das velocidades
                mean_v = sum(velocities) / len(velocities)
                var = sum((v - mean_v) ** 2 for v in velocities) / len(velocities)
                joint_stds.append(var ** 0.5)
        if joint_stds:
            std_windows.append(sum(joint_stds) / len(joint_stds))
        else:
            std_windows.append(0.0)

    # Persistência: streak de frames com std > min_std
    findings: list[PosturalFinding] = []
    consecutive = 0
    streak_start: int | None = None
    worst_std = 0.0

    for idx, std_val in enumerate(std_windows):
        frame_idx = idx + window_frames - 1
        if std_val > min_std:
            if consecutive == 0:
                streak_start = frame_idx
            consecutive += 1
            worst_std = max(worst_std, std_val)
            if consecutive >= persistence_frames and streak_start is not None:
                if not findings:  # emite apenas 1 finding por streak
                    score = min(1.0, worst_std / (min_std * 2))
                    findings.append(PosturalFinding(
                        finding_type="SEIZURE",
                        joint_name=None,
                        measured_angle=round(worst_std, 4),
                        expected_angle=min_std,
                        duration_s=round(consecutive / max(fps, 1.0), 1),
                        frame_index=streak_start,
                        score=round(score, 3),
                        description=(
                            f"Convulsão/espasmo detectado "
                            f"(std velocidade angular = {worst_std:.4f}, "
                            f"{len(_JOINT_TRIPLETS)} articulações, "
                            f"{consecutive / max(fps, 1.0):.1f}s)."
                        ),
                    ))
        else:
            consecutive = 0
            streak_start = None
            worst_std = 0.0

    return findings


# --------------------------------------------------------------------------- #
# Detector de agitação — mudanças de posição por minuto (ITER2-05)
# --------------------------------------------------------------------------- #
def detect_agitation(
    frames: list[PoseFrame | None],
    fps: float,
    window_frames: int = 30,
    min_changes_per_minute: int = 30,
    min_total_frames: int = 120,
) -> list[PosturalFinding]:
    """Deteta agitação psicomotora via frequência de mudanças de posição.

    Divide a timeline em janelas de ``window_frames``, calcula o Y médio
    dos quadris em cada janela, e conta quantas vezes a posição muda
    significativamente (|ΔY| > 0.03) entre janelas consecutivas.
    Se a taxa exceder ``min_changes_per_minute`` mudanças/min, emite
    um finding "AGITATION".
    """
    from pipelines.video.pose_features import hip_center, _upper_body_center

    if len(frames) < min_total_frames:
        return []

    # Y médio por janela
    window_y: list[float | None] = []
    for start in range(0, len(frames), window_frames):
        end = min(start + window_frames, len(frames))
        y_vals: list[float] = []
        for f in frames[start:end]:
            if f is None:
                continue
            center = hip_center(f)
            if center is None:
                center = _upper_body_center(f)
            if center is not None:
                y_vals.append(center[1])
        if y_vals:
            window_y.append(sum(y_vals) / len(y_vals))
        else:
            window_y.append(None)

    # Conta mudanças entre janelas consecutivas
    changes = 0
    for i in range(1, len(window_y)):
        prev_y = window_y[i - 1]
        curr_y = window_y[i]
        if prev_y is not None and curr_y is not None:
            if abs(curr_y - prev_y) > 0.03:
                changes += 1

    total_seconds = len(frames) / max(fps, 1.0)
    rate_per_minute = changes / (total_seconds / 60.0)

    findings: list[PosturalFinding] = []
    if rate_per_minute > min_changes_per_minute:
        score = min(1.0, rate_per_minute / (min_changes_per_minute * 2))
        findings.append(PosturalFinding(
            finding_type="AGITATION",
            joint_name=None,
            measured_angle=round(rate_per_minute, 1),
            expected_angle=float(min_changes_per_minute),
            duration_s=round(total_seconds, 1),
            frame_index=0,
            score=round(score, 3),
            description=(
                f"Agitação psicomotora detectada "
                f"({rate_per_minute:.0f} mudanças/min, "
                f"threshold {min_changes_per_minute}/min, "
                f"{total_seconds:.0f}s analisados)."
            ),
        ))

    return findings


# --------------------------------------------------------------------------- #
# Detector de saída do leito — Y subindo + ΔX (ITER2-06)
# --------------------------------------------------------------------------- #
def detect_bed_exit(
    frames: list[PoseFrame | None],
    fps: float,
    window_frames: int = 60,
    min_delta_y: float = -0.10,
    min_delta_x: float = 0.05,
    min_total_frames: int = 120,
) -> list[PosturalFinding]:
    """Deteta saída do leito em pessoa previamente deitada.

    Só se aplica a pessoas classificadas como recumbent. Calcula a diferença
    de Y médio e o deslocamento lateral total entre dois blocos de 30 frames
    (janela total de 60 frames). Se a pessoa sobe (ΔY < 0) e se desloca
    lateralmente, emite um finding "BED_EXIT".
    """
    from pipelines.video.pose_features import (
        hip_center,
        is_recumbent,
        lateral_displacement,
        _upper_body_center,
    )

    if len(frames) < min_total_frames:
        return []

    if not is_recumbent(frames):
        return []

    # Divide em dois blocos de 30 frames cada (janela total = 60)
    half = window_frames // 2
    early_frames = frames[-window_frames:-half] if len(frames) > window_frames else frames[:half]
    late_frames = frames[-half:]

    # Y médio do bloco inicial
    early_y: list[float] = []
    for f in early_frames:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is not None:
            early_y.append(center[1])

    # Y médio do bloco final
    late_y: list[float] = []
    for f in late_frames:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is not None:
            late_y.append(center[1])

    if len(early_y) < 5 or len(late_y) < 5:
        return []

    avg_early_y = sum(early_y) / len(early_y)
    avg_late_y = sum(late_y) / len(late_y)
    delta_y = avg_late_y - avg_early_y  # negativo = subindo na imagem

    # Deslocamento lateral total no período
    recent = frames[-window_frames:] if len(frames) > window_frames else frames
    dx_list = lateral_displacement(recent)
    valid_dx = [v for v in dx_list if v is not None]
    total_dx = sum(valid_dx) if valid_dx else 0.0

    findings: list[PosturalFinding] = []
    if delta_y < min_delta_y and total_dx > min_delta_x:
        score = min(1.0, abs(delta_y) / (abs(min_delta_y) * 2))
        duration = window_frames / max(fps, 1.0)
        findings.append(PosturalFinding(
            finding_type="BED_EXIT",
            joint_name=None,
            measured_angle=round(abs(delta_y), 3),
            expected_angle=abs(min_delta_y),
            duration_s=round(duration, 1),
            frame_index=max(0, len(frames) - window_frames),
            score=round(score, 3),
            description=(
                f"Saída do leito detectada "
                f"(ΔY = {delta_y:.3f}, ΔX = {total_dx:.3f}, "
                f"{duration:.1f}s)."
            ),
        ))

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
    min_vertical_velocity: float = 0.02,
    all_poses_per_frame: list[list[PoseFrame | None]] | None = None,
    n_pessoas: int | None = None,
) -> tuple[str, int | None, float, str, int | None, int | None]:
    """Validação dinâmica de queda multi-pessoa com agrupamento por track_id.

    Agrupa as poses de todos os frames por ``track_id`` (não por índice
    posicional), garantindo que cada pessoa real tem a sua própria timeline
    independente. Pessoas já deitadas (``is_recumbent()``) são excluídas
    da detecção de queda — um acompanhante que se senta não dispara alarme.

    Em cenas multi-pessoa (``n_pessoas > 1``), os thresholds são elevados
    automaticamente para reduzir falsos positivos.

    Devolve ``(verdict, frame_idx, velocity_score, description, track_id, peak_vy_frame)``.
    ``track_id`` é o identificador persistente da pessoa que caiu (``None`` se
    tracking não disponível ou fallback de frame inteiro).
    """
    if fall_verdict != "queda":
        return (fall_verdict, fall_frame_idx, 0.0, "", None, None)

    from pipelines.video.pose_features import (
        group_poses_by_track_id,
        is_recumbent,
        lateral_displacement,
        max_vertical_velocity,
        torso_height,
        total_displacement,
        trunk_tilt,
        vertical_velocity_robust,
        was_initially_recumbent,
    )

    # Thresholds base (single-person, calibrados em torso-heights contra URFD)
    # Sem normalização (torso_height=None), comportam-se como os absolutos antigos.
    _MIN_TILT_FOR_FALL = 25.0
    _MIN_TOTAL_DISPLACEMENT = 0.20
    _MIN_VERTICAL_VELOCITY_FLOOR = 0.01

    # Determina se é cena multi-pessoa para thresholds adaptativos (C2)
    effective_n_pessoas = n_pessoas
    if effective_n_pessoas is None and all_poses_per_frame:
        effective_n_pessoas = max(
            (len(p) for p in all_poses_per_frame if p), default=0
        )

    if effective_n_pessoas is not None and effective_n_pessoas > 1:
        _MIN_TILT_FOR_FALL = 35.0
        _MIN_TOTAL_DISPLACEMENT = 0.30
        min_vertical_velocity = max(min_vertical_velocity, 0.04)
    else:
        min_vertical_velocity = max(min_vertical_velocity, _MIN_VERTICAL_VELOCITY_FLOOR)

    best_vy = 0.0
    best_description = ""
    best_track_id: int | None = None
    best_peak_frame: int | None = None

    # Estratégia primária: agrupar por track_id (A1)
    if all_poses_per_frame:
        person_timelines = group_poses_by_track_id(all_poses_per_frame)

        if person_timelines:
            # Analisa cada pessoa real independentemente
            for track_id, person_frames in person_timelines.items():
                # Exclui apenas pessoas que JÁ estavam deitadas no INÍCIO
                # (não sofreram queda durante este vídeo).
                # Usa was_initially_recumbent (primeiros 30 frames), não
                # is_recumbent (últimos 90 frames) — uma pessoa que caiu
                # durante o vídeo está deitada no final, e é exatamente
                # essa transição que queremos detectar.
                if was_initially_recumbent(person_frames):
                    continue

                vy_list = vertical_velocity_robust(person_frames)

                tilts = [
                    t for f in person_frames if f is not None
                    for t in [trunk_tilt(f)] if t is not None
                ]
                max_tilt = max(tilts) if tilts else 0.0

                # Normalização por altura do tronco: Vy e deslocamento em
                # body-heights (dividir pelo torso), tornando os thresholds
                # independentes da distância da câmara. Os thresholds atuais
                # foram calibrados com torso ≈ 0.14 (URFD típico).
                torso_vals = [
                    th for f in person_frames if f is not None
                    for th in [torso_height(f)] if th is not None and th > 0.01
                ]
                norm_factor = (
                    sum(torso_vals) / len(torso_vals) if torso_vals else 0.14
                )

                max_vy = max_vertical_velocity(vy_list) / norm_factor
                total_dy = total_displacement(vy_list) / norm_factor

                # Queda = Pico Vy + deslocamento total + tilt
                if (
                    max_vy >= min_vertical_velocity
                    and total_dy >= _MIN_TOTAL_DISPLACEMENT
                    and max_tilt >= _MIN_TILT_FOR_FALL
                ):
                    if max_vy > best_vy:
                        best_vy = max_vy
                        best_track_id = track_id
                        valid_vy = [
                            (i, v) for i, v in enumerate(vy_list) if v is not None
                        ]
                        if valid_vy:
                            best_peak_frame = max(valid_vy, key=lambda x: x[1])[0]
                        best_description = (
                            f"Queda abrupta detectada no frame {best_peak_frame} "
                            f"(variação de velocidade vertical Vy = {max_vy:.3f}/frame, "
                            f"inclinação do tronco = {max_tilt:.0f}°"
                            + (f", track_id={track_id}" if track_id is not None else "")
                            + ")."
                        )
                    continue

                # Fallback: rolamento/escorregamento
                dx_list = lateral_displacement(person_frames)
                valid_dx = [v for v in dx_list if v is not None]
                max_dx = max(valid_dx) if len(valid_dx) >= 5 else 0.0

                if max_dx > 0.05 and max_vy > 0.05:
                    combined = (max_dx + max_vy) / 2.0
                    if combined > best_vy:
                        best_vy = combined
                        best_track_id = track_id
                        valid_vy = [
                            (i, v) for i, v in enumerate(vy_list) if v is not None
                        ]
                        best_peak_frame = (
                            max(valid_vy, key=lambda x: x[1])[0]
                            if valid_vy else None
                        )
                        best_description = (
                            f"Queda por rolamento/escorregamento detectada "
                            f"(deslocamento lateral ΔX = {max_dx:.3f}, "
                            f"Vy = {max_vy:.3f}"
                            + (f", track_id={track_id}" if track_id is not None else "")
                            + ")."
                        )

            if best_vy >= min_vertical_velocity:
                return (
                    "queda", fall_frame_idx, round(best_vy, 3),
                    best_description, best_track_id, best_peak_frame,
                )

            return (
                "adl", None, round(best_vy, 3),
                "Postura reclinada/estática detectada — sem evidência de queda "
                f"(Vy max = {best_vy:.3f}/frame, abaixo do limiar {min_vertical_velocity}).",
                None, None,
            )

    # Fallback: sem tracking multi-pessoa — usa a velocidade já calculada
    # sobre os frames do ground_person (comportamento retrocompatível)
    if not all_poses_per_frame or not person_timelines:
        person_frames: list[PoseFrame | None] = []
        if all_poses_per_frame:
            person_frames = [
                poses[0] if poses and len(poses) > 0 else None
                for poses in all_poses_per_frame
            ]
        else:
            person_frames = []

        # Exclui apenas se já estava deitado no INÍCIO (fallback)
        if was_initially_recumbent(person_frames):
            return (
                "adl", None, 0.0,
                "Postura reclinada/estática detectada — pessoa já se encontrava "
                "deitada no início da análise.",
                None, None,
            )

        vy_list = vertical_velocity_robust(person_frames) if person_frames else velocities

        tilts = [
            t for f in person_frames if f is not None
            for t in [trunk_tilt(f)] if t is not None
        ]
        max_tilt = max(tilts) if tilts else 0.0

        max_vy = max_vertical_velocity(vy_list)
        total_dy = total_displacement(vy_list)

        if (
            max_vy >= min_vertical_velocity
            and total_dy >= _MIN_TOTAL_DISPLACEMENT
            and max_tilt >= _MIN_TILT_FOR_FALL
        ):
            valid_vy = [(i, v) for i, v in enumerate(vy_list) if v is not None]
            peak_frame = max(valid_vy, key=lambda x: x[1])[0] if valid_vy else None
            return (
                "queda", fall_frame_idx, round(max_vy, 3),
                f"Queda abrupta detectada no frame {peak_frame} "
                f"(variação de velocidade vertical Vy = {max_vy:.3f}/frame, "
                f"inclinação do tronco = {max_tilt:.0f}°).",
                None, peak_frame,
            )

    return (
        "adl", None, round(best_vy, 3),
        "Postura reclinada/estática detectada — sem evidência de queda "
        f"(Vy max = {best_vy:.3f}/frame, abaixo do limiar {min_vertical_velocity}).",
        None, None,
    )


def _compute_net_y_descent(
    person_frames: list[PoseFrame | None],
) -> float:
    """Deslocamento vertical líquido do primeiro ao último frame válido.

    Valores positivos indicam descida (Y aumenta = pessoa desce na imagem).
    Usado como gate adicional no Vy-primary: uma queda real produz descida
    líquida significativa (>0.15), enquanto movimentos normais que disparam
    o Vy-primary por glitches têm pouco ou nenhum deslocamento líquido.

    Devolve 0.0 se não houver frames válidos suficientes.
    """
    from pipelines.video.pose_features import hip_center, _upper_body_center

    first_y: float | None = None
    last_y: float | None = None

    for f in person_frames:
        if f is None:
            continue
        center = hip_center(f)
        if center is None:
            center = _upper_body_center(f)
        if center is None:
            continue
        if first_y is None:
            first_y = center[1]
        last_y = center[1]

    if first_y is None or last_y is None:
        return 0.0
    return last_y - first_y


def analyze_all_persons(
    all_poses_per_frame: list[list[PoseFrame | None]],
    fps: float = 30.0,
    joint_targets: list[JointTarget] | None = None,
    fall_threshold: float = 0.55,
    persistence_frames: int = 1,
) -> tuple[str, float, list[PosturalFinding], dict]:
    """Pipeline multi-pessoa: analisa cada pessoa com detector de queda + vigilância.

    Itera ``group_poses_by_track_id()`` — para cada pessoa identificada,
    classifica o papel via ``classify_person_role()`` e despacha os
    detectores adequados:

    - **Detector de queda** (2 estágios: amplitude → velocidade) executa
      para TODAS as pessoas, exceto as que já estavam deitadas no INÍCIO
      da sequência (``was_initially_recumbent()``). Uma pessoa que começa
      de pé e cai durante o vídeo passa pelo detector.
    - **Vigilância** (agitation, bed_exit) executa adicionalmente para
      pessoas classificadas como "recumbent".
    - "unknown" → ignorada

    Consolida os findings de todas as pessoas. Sem tracking ativo, faz
    fallback ao comportamento Iteração 1 (single-person).

    Returns:
        (resumo, pontuacao, consolidated_findings, details_dict)
    """
    from pipelines.video.pose_features import (
        classify_person_role,
        group_poses_by_track_id,
    )

    from pipelines.video.pose_features import (
        classify_person_role,
        group_poses_by_track_id,
        is_recumbent,
        max_consecutive_above,
        max_vertical_velocity,
        total_displacement,
        vertical_velocity_robust,
        was_initially_recumbent,
        windowed_features,
    )

    all_findings: list[PosturalFinding] = []
    details: dict = {"pessoas_analisadas": 0, "por_papel": {}}

    person_timelines = group_poses_by_track_id(all_poses_per_frame)

    if not person_timelines:
        # Fallback single-person (sem tracking)
        return ("Sem alterações detectadas.", 0.0, [], details)

    # Conta apenas pessoas reais (com track_id), não ghosts do MediaPipe
    n_pessoas_reais = len(person_timelines)

    for track_id, person_frames in person_timelines.items():
        role = classify_person_role(person_frames)
        details["pessoas_analisadas"] += 1
        details["por_papel"][track_id] = role

        # -- Detector de queda: executa para TODAS as pessoas, exceto
        #    as que JÁ estavam deitadas no início da sequência.
        #    Uma pessoa que começa de pé e cai durante o vídeo era
        #    "standing" no início e "recumbent" no final — o detector
        #    captura precisamente essa transição.
        if not was_initially_recumbent(person_frames):
            windows = windowed_features(person_frames, 30, stride=15)
            fall_verdict, fall_frame_idx = classify_with_persistence(
                windows, fall_threshold, persistence_frames,
            )

            # Via complementar: quedas lentas (ex.: fall-05) podem ter
            # amplitude abaixo do threshold mas deslocamento total forte
            # e terminar com a pessoa no chão. Só ativa quando o Estágio 1
            # NÃO detetou e a pessoa está recumbent no final.
            vy_fallback = False
            if fall_verdict != "queda":
                velocities_fb = vertical_velocity_robust(person_frames)
                max_vy_fb = max_vertical_velocity(velocities_fb)
                total_dy_fb = total_displacement(velocities_fb)
                # Vy-primary: requer descida sustentada (≥2 frames consecutivos
                # com Vy>0.02) + deslocamento total + deslocamento líquido em Y.
                # Filtra glitches de detecção (pico isolado) que são comuns em ADL.
                consecutive_descending = max_consecutive_above(velocities_fb, 0.02)
                y_descent = _compute_net_y_descent(person_frames)
                if (consecutive_descending >= 2 and max_vy_fb >= 0.04
                    and total_dy_fb >= 0.30 and y_descent >= 0.15
                    and is_recumbent(person_frames)):
                    vy_fallback = True
                    fall_verdict = "queda"
                    valid_vy = [(i, v) for i, v in enumerate(velocities_fb) if v is not None and v > 0.01]
                    fall_frame_idx = max(valid_vy, key=lambda x: x[1])[0] if valid_vy else 0

            if fall_verdict == "queda":
                velocities = vertical_velocity_robust(person_frames)
                min_vy = 0.02 if not vy_fallback else 0.04
                verdict, _, vy_score, desc, tid, peak = validate_fall_dynamic(
                    fall_verdict, fall_frame_idx, velocities, min_vy,
                    all_poses_per_frame=all_poses_per_frame,
                    n_pessoas=n_pessoas_reais,
                )
                if verdict == "queda":
                    fall_desc = desc
                    if vy_fallback:
                        fall_desc = f"[Vy-primary] {desc}"
                    all_findings.append(PosturalFinding(
                        finding_type="FALL_DETECTED",
                        joint_name=None,
                        measured_angle=vy_score,
                        expected_angle=0.10,
                        duration_s=0.0,
                        frame_index=peak or 0,
                        score=min(1.0, vy_score),
                        description=fall_desc,
                    ))

        # -- Vigilância contínua para pessoa deitada
        if role == "recumbent":
            ag = detect_agitation(person_frames, fps)
            be = detect_bed_exit(person_frames, fps)
            all_findings.extend(ag)
            all_findings.extend(be)

    # Consolida: todos os findings (queda + novos detectores)
    fall_detected = any(f.finding_type == "FALL_DETECTED" for f in all_findings)
    resumo, pontuacao, consolidated = sumarizar_achados_video(
        [], [], fall_detected,
    )

    # Adiciona TODOS os findings ao consolidated (incluindo FALL_DETECTED)
    for f in all_findings:
        consolidated.append(f)
        pontuacao = max(pontuacao, f.score)

    if not consolidated:
        return ("Sem alterações detectadas.", 0.0, [], details)

    return (resumo, pontuacao, consolidated, details)


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

    # --- Novos detectores (ITER2: SEIZURE, AGITATION, BED_EXIT) ---
    for f in postural_findings:
        if f.finding_type == "SEIZURE":
            partes.append(
                f"Convulsão/espasmo detectado "
                f"(std={f.measured_angle:.4f}, {f.duration_s}s)"
            )
            pontuacao = max(pontuacao, f.score)
        elif f.finding_type == "AGITATION":
            partes.append(
                f"Agitação psicomotora detectada "
                f"({f.measured_angle:.0f} mudanças/min)"
            )
            pontuacao = max(pontuacao, f.score)
        elif f.finding_type == "BED_EXIT":
            partes.append(
                f"Saída do leito detectada "
                f"(ΔY={f.measured_angle:.3f}, {f.duration_s}s)"
            )
            pontuacao = max(pontuacao, f.score)

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
    track_id: int | None = None,
) -> Evidence:
    """Gera a evidência de queda (frame anotado + metadados) no contrato único de evidência.

    ``track_id`` identifica inequivocamente a pessoa que disparou a queda
    (rastreada via IoU entre frames consecutivos). É incluído no sidecar de
    metadados para correlacionar a evidência visual com a identidade da pessoa
    ao longo da sequência.
    """
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
        f"acima do limiar (score {score:.2f})"
        + (f" [track_id={track_id}]" if track_id is not None else ""),
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
            "track_id": track_id,
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
