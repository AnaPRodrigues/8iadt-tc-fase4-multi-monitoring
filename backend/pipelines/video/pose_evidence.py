"""Evidência visual anotada — esqueleto com articulações destacadas e ângulos.

Desenha todos os landmarks do MediaPipe Pose (33 pontos) sobre o frame real,
destacando as articulações envolvidas em achados posturais com cores e ângulos
sobrepostos. Complementa ``draw_keypoints`` (pose_detector.py) que desenha só os
landmarks — esta função adiciona contexto clínico (ângulos, cores por severidade).
"""

from pathlib import Path

import cv2

from pipelines.video.models import PoseFrame, PosturalFinding

_MIN_VISIBILITY = 0.5

# Conexões ósseas (pares de índices de landmarks) para desenhar o esqueleto.
_BONE_CONNECTIONS = [
    # Tronco
    (11, 12), (11, 23), (12, 24), (23, 24),
    # Braço esquerdo
    (11, 13), (13, 15),
    # Braço direito
    (12, 14), (14, 16),
    # Perna esquerda
    (23, 25), (25, 27),
    # Perna direita
    (24, 26), (26, 28),
]

# Cores BGR (OpenCV)
_COLOR_BLUE = (255, 0, 0)       # Esqueleto normal
_COLOR_YELLOW = (0, 255, 255)    # Atenção (POSTURAL_DEVIATION)
_COLOR_RED = (0, 0, 255)         # Grave (TRUNK_TILT, FALL_DETECTED)
_COLOR_WHITE = (255, 255, 255)   # Texto
_COLOR_LIGHT_BLUE = (255, 255, 128)  # Conexões ósseas


def _color_for_finding(finding_type: str) -> tuple[int, int, int]:
    if finding_type in ("TRUNK_TILT", "FALL_DETECTED"):
        return _COLOR_RED
    return _COLOR_YELLOW


def _affected_landmarks(findings: list[PosturalFinding]) -> set[int]:
    """Landmarks mencionados nos findings (para destacar no desenho).

    Para ``TRUNK_TILT``: ombros (11, 12) e quadris (23, 24).
    Para ``FALL_DETECTED``: quadris (23, 24) — centro de massa.
    """
    affected: set[int] = set()
    for f in findings:
        if f.finding_type == "TRUNK_TILT":
            affected.update([11, 12, 23, 24])
        elif f.finding_type == "FALL_DETECTED":
            affected.update([23, 24])
        elif f.finding_type == "POSTURAL_DEVIATION" and f.joint_name:
            # joint_name como "knee_left" — não temos mapeamento inverso aqui.
            # Por simplicidade, destacamos todos os landmarks do esqueleto inferior.
            affected.update([23, 24, 25, 26, 27, 28])
    return affected


def draw_annotated_frame(
    frame_path: Path,
    pose_frame: PoseFrame,
    findings: list[PosturalFinding],
    output_path: Path,
) -> Path:
    """Desenha o esqueleto completo com articulações anómalas destacadas.

    - Landmarks válidos (visibilidade ≥ 0.5): círculo azul (normal) ou
      amarelo/vermelho (anómalo, conforme o tipo de finding).
    - Conexões ósseas em azul claro.
    - Para ``TRUNK_TILT``: linha da espinha (ombros → quadris) em vermelho
      com o ângulo de inclinação sobreposto.
    - Para ``POSTURAL_DEVIATION``: ângulo medido sobreposto perto da
      articulação afetada.
    """
    frame_path = Path(frame_path)
    image = cv2.imread(str(frame_path))
    if image is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")

    height, width = image.shape[:2]
    affected = _affected_landmarks(findings)

    # Seleciona uma cor principal para este conjunto de findings
    finding_types = {f.finding_type for f in findings}
    if "FALL_DETECTED" in finding_types or "TRUNK_TILT" in finding_types:
        highlight_color = _COLOR_RED
    elif "POSTURAL_DEVIATION" in finding_types:
        highlight_color = _COLOR_YELLOW
    else:
        highlight_color = _COLOR_BLUE

    # Desenha landmarks
    for i, (x, y, _z, visibility) in enumerate(pose_frame.landmarks):
        if visibility < _MIN_VISIBILITY:
            continue
        px, py = int(x * width), int(y * height)
        color = highlight_color if i in affected else _COLOR_BLUE
        radius = 6 if i in affected else 4
        cv2.circle(image, (px, py), radius, color, -1)

    # Desenha conexões ósseas
    for a, b in _BONE_CONNECTIONS:
        xa, ya, _, va = pose_frame.landmarks[a]
        xb, yb, _, vb = pose_frame.landmarks[b]
        if va < _MIN_VISIBILITY or vb < _MIN_VISIBILITY:
            continue
        cv2.line(
            image,
            (int(xa * width), int(ya * height)),
            (int(xb * width), int(yb * height)),
            _COLOR_LIGHT_BLUE,
            2,
        )

    # Desenha linha da espinha + ângulo para TRUNK_TILT
    for f in findings:
        if f.finding_type == "TRUNK_TILT":
            # Ponto médio ombros
            sx = (pose_frame.landmarks[11][0] + pose_frame.landmarks[12][0]) / 2
            sy = (pose_frame.landmarks[11][1] + pose_frame.landmarks[12][1]) / 2
            hx = (pose_frame.landmarks[23][0] + pose_frame.landmarks[24][0]) / 2
            hy = (pose_frame.landmarks[23][1] + pose_frame.landmarks[24][1]) / 2
            cv2.line(
                image,
                (int(sx * width), int(sy * height)),
                (int(hx * width), int(hy * height)),
                _COLOR_RED,
                3,
            )
            mid_x = int((sx + hx) / 2 * width)
            mid_y = int((sy + hy) / 2 * height)
            cv2.putText(
                image,
                f"{f.measured_angle:.0f} deg",
                (mid_x + 10, mid_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                _COLOR_RED,
                2,
            )

        elif f.finding_type == "POSTURAL_DEVIATION" and f.joint_name:
            # Ângulo sobre o landmark b (vértice)
            # Usamos o landmark do joelho ou cotovelo como aproximação
            if "knee" in f.joint_name:
                b_idx = 25 if "left" in f.joint_name else 26
            elif "elbow" in f.joint_name:
                b_idx = 13 if "left" in f.joint_name else 14
            else:
                b_idx = 25  # fallback
            bx, by, _, vb = pose_frame.landmarks[b_idx]
            if vb >= _MIN_VISIBILITY:
                px, py = int(bx * width), int(by * height)
                cv2.putText(
                    image,
                    f"{f.measured_angle:.0f} deg",
                    (px + 10, py - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    highlight_color,
                    2,
                )

    # Bounding box de destaque ao redor da pessoa (para clareza no relatório)
    valid_points = [
        (int(x * width), int(y * height))
        for x, y, _z, v in pose_frame.landmarks if v >= _MIN_VISIBILITY
    ]
    if len(valid_points) >= 5:
        xs = [p[0] for p in valid_points]
        ys = [p[1] for p in valid_points]
        padding = 15
        cv2.rectangle(
            image,
            (max(0, min(xs) - padding), max(0, min(ys) - padding)),
            (min(width, max(xs) + padding), min(height, max(ys) + padding)),
            highlight_color, 2,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path
