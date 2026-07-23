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
