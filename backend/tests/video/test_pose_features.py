"""Testes de `pose_features.windowed_features` -- derivados de VIDEO-02 e do
edge case VIDEO-13 (frame sem pessoa excluído da janela)."""

import math

import pytest

from pipelines.video.models import PoseFrame
from pipelines.video.pose_features import windowed_features

_N_LANDMARKS = 33


def _make_frame(left_hip_xy: tuple[float, float], right_hip_xy: tuple[float, float]) -> PoseFrame:
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(_N_LANDMARKS)]
    landmarks[23] = (left_hip_xy[0], left_hip_xy[1], 0.0, 0.9)
    landmarks[24] = (right_hip_xy[0], right_hip_xy[1], 0.0, 0.9)
    return PoseFrame(landmarks=landmarks)


def test_janela_com_movimento_estavel_tem_baixa_amplitude():
    # Quadril praticamente parado ao longo de 10 frames (jitter mínimo).
    frames = [_make_frame((0.50, 0.50), (0.52, 0.50)) for _ in range(10)]

    windows = windowed_features(frames, window_size=10)

    assert len(windows) == 1
    assert windows[0].center_of_mass_amplitude < 0.02
    assert windows[0].velocity < 0.02


def test_janela_com_queda_simulada_tem_amplitude_muito_maior():
    # Variação abrupta e conhecida: quadril sobe de y=0.20 para y=0.90.
    frames_estaveis = [_make_frame((0.50, 0.50), (0.52, 0.50)) for _ in range(10)]
    frames_queda = [_make_frame((0.50, y), (0.52, y)) for y in [0.20, 0.90]] + [
        _make_frame((0.50, 0.90), (0.52, 0.90)) for _ in range(8)
    ]

    windows_estavel = windowed_features(frames_estaveis, window_size=10)
    windows_queda = windowed_features(frames_queda, window_size=10)

    assert windows_queda[0].center_of_mass_amplitude > 0.5
    assert windows_queda[0].center_of_mass_amplitude > windows_estavel[0].center_of_mass_amplitude


def test_amplitude_e_velocidade_batem_com_calculo_manual():
    # Dois pontos exatos: centro de massa (0.5, 0.2) -> (0.5, 0.9).
    frames = [_make_frame((0.5, 0.20), (0.5, 0.20)), _make_frame((0.5, 0.90), (0.5, 0.90))]

    windows = windowed_features(frames, window_size=2)

    esperado = math.dist((0.5, 0.20), (0.5, 0.90))
    assert windows[0].center_of_mass_amplitude == esperado
    assert windows[0].velocity == esperado  # um único deslocamento = a própria distância


def test_frames_none_intercalados_sao_excluidos_sem_quebrar_a_janela():
    valido_a = _make_frame((0.50, 0.50), (0.52, 0.50))
    valido_b = _make_frame((0.50, 0.55), (0.52, 0.55))
    frames_com_none = [valido_a, None, valido_b, None]
    frames_sem_none = [valido_a, valido_b]

    windows_com_none = windowed_features(frames_com_none, window_size=4)
    windows_sem_none = windowed_features(frames_sem_none, window_size=2)

    assert len(windows_com_none) == 1
    # O resultado da janela com None intercalados deve ser idêntico ao cálculo
    # feito só sobre os frames válidos -- prova que o None foi excluído, não
    # tratado como zero/posição inventada.
    com_none = windows_com_none[0]
    sem_none = windows_sem_none[0]
    assert com_none.center_of_mass_amplitude == sem_none.center_of_mass_amplitude
    assert com_none.velocity == sem_none.velocity


def test_janela_sem_nenhum_frame_valido_nao_e_gerada():
    frames = [None, None, None]

    windows = windowed_features(frames, window_size=3)

    assert windows == []


def test_assimetria_reflete_diferenca_entre_quadris():
    frame_simetrico = _make_frame((0.50, 0.50), (0.52, 0.50))
    frame_assimetrico = _make_frame((0.50, 0.30), (0.52, 0.70))

    windows_simetrico = windowed_features([frame_simetrico, frame_simetrico], window_size=2)
    windows_assimetrico = windowed_features([frame_assimetrico, frame_assimetrico], window_size=2)

    assert windows_simetrico[0].asymmetry == 0.0
    assert windows_assimetrico[0].asymmetry == pytest.approx(0.4)
