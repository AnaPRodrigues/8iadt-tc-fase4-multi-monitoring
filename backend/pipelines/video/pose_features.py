"""Métricas de movimento por janela, derivadas do centro de massa.

A fórmula exata de assimetria postural não é fixada a priori
("assimetria postural" é descrito só qualitativamente). Adotada a
diferença absoluta entre a altura (y) dos dois landmarks de quadril (23/24) --
mesmos landmarks usados para o centro de massa, sem introduzir um terceiro par
de pontos não mencionado no design. Calibrável na prática, mesmo princípio de
threshold usado para detecção de queda (ver `pose_detector.py`).
"""

import math

from pipelines.video.models import MovementWindow, PoseFrame

_LEFT_HIP = 23
_RIGHT_HIP = 24


def _center_of_mass(frame: PoseFrame) -> tuple[float, float]:
    lx, ly, _, _ = frame.landmarks[_LEFT_HIP]
    rx, ry, _, _ = frame.landmarks[_RIGHT_HIP]
    return ((lx + rx) / 2.0, (ly + ry) / 2.0)


def _asymmetry(frame: PoseFrame) -> float:
    _, ly, _, _ = frame.landmarks[_LEFT_HIP]
    _, ry, _, _ = frame.landmarks[_RIGHT_HIP]
    return abs(ly - ry)


def windowed_features(frames: list[PoseFrame | None], window_size: int) -> list[MovementWindow]:
    """Calcula amplitude/velocidade do centro de massa e assimetria por janela.

    Frames `None` (sem pessoa detectada) são excluídos do cálculo da
    janela em que caem, sem quebrar as demais. Uma janela sem nenhum frame
    válido não é gerada -- não existe `MovementWindow` com valores inventados.
    `end_frame` é inclusivo (último índice de frame coberto pela janela).
    """
    if window_size <= 0:
        raise ValueError("window_size precisa ser positivo")

    windows: list[MovementWindow] = []
    for start in range(0, len(frames), window_size):
        end = min(start + window_size, len(frames))
        indices_validos = [i for i in range(start, end) if frames[i] is not None]
        if not indices_validos:
            continue

        pontos = [_center_of_mass(frames[i]) for i in indices_validos]

        if len(pontos) >= 2:
            amplitude = max(
                math.dist(pontos[a], pontos[b])
                for a in range(len(pontos))
                for b in range(a + 1, len(pontos))
            )
            deslocamentos = [math.dist(pontos[i], pontos[i - 1]) for i in range(1, len(pontos))]
            velocidade = sum(deslocamentos) / len(deslocamentos)
        else:
            amplitude = 0.0
            velocidade = 0.0

        assimetria = sum(_asymmetry(frames[i]) for i in indices_validos) / len(indices_validos)

        windows.append(
            MovementWindow(
                start_frame=start,
                end_frame=end - 1,
                center_of_mass_amplitude=amplitude,
                velocity=velocidade,
                asymmetry=assimetria,
            )
        )

    return windows


# --------------------------------------------------------------------------- #
# Constantes compartilhadas
# --------------------------------------------------------------------------- #
_MIN_VISIBILITY = 0.5
_SHOULDER_LEFT = 11
_SHOULDER_RIGHT = 12
_HIP_LEFT = 23
_HIP_RIGHT = 24


# --------------------------------------------------------------------------- #
# Velocidade vertical do centro de massa (filtro anti-estático de queda)
# --------------------------------------------------------------------------- #
def vertical_velocity(
    frames: list[PoseFrame | None],
) -> list[float | None]:
    """Velocidade vertical do centro de massa (quadril) por frame.

    Calcula $V_y = (Y_{atual} - Y_{anterior}) / 1$ frame. O eixo Y do
    MediaPipe cresce para baixo — uma queda real produz um pico positivo
    de $V_y$ (o quadril desce rapidamente na imagem).

    Devolve ``None`` para frames sem pessoa ou sem frame anterior válido.
    """
    velocities: list[float | None] = []
    prev_y: float | None = None

    for frame in frames:
        if frame is None:
            velocities.append(None)
            prev_y = None
            continue

        # Centro de massa: ponto médio dos quadris (23, 24)
        ly = frame.landmarks[23][1]
        ry = frame.landmarks[24][1]
        lv = frame.landmarks[23][3]
        rv = frame.landmarks[24][3]
        if lv < _MIN_VISIBILITY or rv < _MIN_VISIBILITY:
            velocities.append(None)
            prev_y = None
            continue

        current_y = (ly + ry) / 2.0

        if prev_y is not None:
            vy = current_y - prev_y  # positivo = descendo (queda)
        else:
            vy = None

        velocities.append(vy)
        prev_y = current_y

    return velocities


def max_vertical_velocity(
    velocities: list[float | None], window_frames: int = 15
) -> float:
    """Maior velocidade vertical **sustentada e direcional** no sinal.

    Exige pelo menos 5 frames com $V_y > 0.10$ **no mesmo sentido** (positivo =
    descida). Valores negativos (subida) são ignorados — uma pessoa a caminhar
    oscila para cima e para baixo, mas uma queda real só tem descida abrupta.

    Filtra jitter, caminhada e ajustes posturais. Devolve a média dos 5
    maiores valores positivos; se não houver 5 acima do piso, devolve 0.0.
    """
    valid = [v for v in velocities if v is not None]
    positive = sorted([v for v in valid if v > 0.10], reverse=True)
    if len(positive) < 5:
        return 0.0
    return sum(positive[:5]) / 5.0
def _min_visibility(frame: PoseFrame, indices: list[int]) -> float:
    """Menor visibilidade entre os landmarks pedidos — gate de qualidade.

    Qualquer landmark com visibilidade < 0.5 invalida o cálculo (POSE-19).
    """
    return min(frame.landmarks[i][3] for i in indices)


def _landmark_xy(frame: PoseFrame, idx: int) -> tuple[float, float]:
    return (frame.landmarks[idx][0], frame.landmarks[idx][1])


def select_ground_person(
    all_poses: list[list[PoseFrame | None]],
) -> list[PoseFrame | None]:
    """Seleciona, por frame, a pessoa com menor Y médio (mais próxima do chão).

    Frames sem nenhuma pessoa → ``None``. Empate → primeira encontrada.
    """
    result: list[PoseFrame | None] = []
    for poses in all_poses:
        valid = [p for p in poses if p is not None]
        if not valid:
            result.append(None)
            continue
        # Pessoa com maior Y médio = mais abaixo na imagem = nível do solo
        best = max(valid, key=lambda p: sum(
            lm[1] for lm in p.landmarks
        ) / len(p.landmarks))
        result.append(best)
    return result


def joint_angle(
    frame: PoseFrame, a: int, b: int, c: int
) -> float | None:
    """Ângulo no landmark ``b`` formado pelos vetores ``a→b`` e ``c→b``.

    Usa o produto escalar: θ = arccos((v1·v2) / (|v1|·|v2|)). Devolve graus.
    ``None`` se qualquer um dos 3 landmarks tiver visibilidade < 0.5.
    """
    if _min_visibility(frame, [a, b, c]) < _MIN_VISIBILITY:
        return None

    ax, ay = _landmark_xy(frame, a)
    bx, by = _landmark_xy(frame, b)
    cx, cy = _landmark_xy(frame, c)

    v1 = (ax - bx, ay - by)
    v2 = (cx - bx, cy - by)

    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = (v1[0] ** 2 + v1[1] ** 2) ** 0.5
    mag2 = (v2[0] ** 2 + v2[1] ** 2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return None

    cos_theta = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_theta))


def trunk_tilt(frame: PoseFrame) -> float | None:
    """Ângulo do eixo da espinha em relação à vertical Y.

    O eixo da espinha vai do ponto médio dos ombros (11/12) ao ponto médio
    dos quadris (23/24). Devolve o ângulo absoluto em graus; ``None`` se
    visibilidade insuficiente.
    """
    if _min_visibility(frame, [_SHOULDER_LEFT, _SHOULDER_RIGHT,
                                  _HIP_LEFT, _HIP_RIGHT]) < _MIN_VISIBILITY:
        return None

    sx = (frame.landmarks[_SHOULDER_LEFT][0] + frame.landmarks[_SHOULDER_RIGHT][0]) / 2
    sy = (frame.landmarks[_SHOULDER_LEFT][1] + frame.landmarks[_SHOULDER_RIGHT][1]) / 2
    hx = (frame.landmarks[_HIP_LEFT][0] + frame.landmarks[_HIP_RIGHT][0]) / 2
    hy = (frame.landmarks[_HIP_LEFT][1] + frame.landmarks[_HIP_RIGHT][1]) / 2

    spine = (hx - sx, hy - sy)
    vertical = (0.0, 1.0)

    dot = spine[0] * vertical[0] + spine[1] * vertical[1]
    mag_spine = (spine[0] ** 2 + spine[1] ** 2) ** 0.5

    if mag_spine == 0:
        return None

    cos_theta = max(-1.0, min(1.0, dot / mag_spine))
    return math.degrees(math.acos(cos_theta))


def joint_angles_per_frame(
    frame: PoseFrame, joints: list[tuple[str, int, int, int]]
) -> dict[str, float | None]:
    """Calcula todos os ângulos configurados para um frame.

    ``joints`` é uma lista de ``(nome, a, b, c)`` — mesma estrutura de
    ``JointTarget``, mas em tupla para esta função não depender do dataclass.
    """
    result: dict[str, float | None] = {}
    for name, a, b, c in joints:
        result[name] = joint_angle(frame, a, b, c)
    return result
