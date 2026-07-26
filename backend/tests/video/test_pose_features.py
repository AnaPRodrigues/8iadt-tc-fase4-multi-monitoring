"""Testes de `pose_features.windowed_features` -- métricas de movimento e o
edge case de frame sem pessoa excluído da janela."""

import math

import pytest

from pipelines.video.models import JointTarget, PoseFrame
from pipelines.video.pose_features import (
    joint_angle,
    joint_angles_per_frame,
    max_vertical_velocity,
    select_ground_person,
    total_displacement,
    trunk_tilt,
    vertical_velocity,
    windowed_features,
)

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


# --------------------------------------------------------------------------- #
# Helpers para os novos testes (ângulos, tilt, multi-person)
# --------------------------------------------------------------------------- #
def _make_full_frame(
    landmarks_override: dict[int, tuple[float, float, float, float]] | None = None,
) -> PoseFrame:
    """Cria um PoseFrame com todos os 33 landmarks em (0.5, 0.5, 0, 0.9).

    ``landmarks_override`` substitui landmarks específicos (ex.: quadril, joelho).
    """
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    if landmarks_override:
        for idx, val in landmarks_override.items():
            landmarks[idx] = val
    return PoseFrame(landmarks=landmarks)


# --------------------------------------------------------------------------- #
# joint_angle
# --------------------------------------------------------------------------- #
def test_joint_angle_90_graus():
    """Joelho em ângulo reto: quadril (0.5, 0.4), joelho (0.5, 0.6), tornozelo (0.3, 0.6)."""
    frame = _make_full_frame({
        23: (0.5, 0.4, 0.0, 0.9),  # hip
        25: (0.5, 0.6, 0.0, 0.9),  # knee
        27: (0.3, 0.6, 0.0, 0.9),  # ankle
    })

    angle = joint_angle(frame, 23, 25, 27)

    assert angle == pytest.approx(90.0, abs=1.0)


def test_joint_angle_180_graus():
    """Perna esticada: landmarks alinhados verticalmente."""
    frame = _make_full_frame({
        23: (0.5, 0.2, 0.0, 0.9),  # hip
        25: (0.5, 0.5, 0.0, 0.9),  # knee
        27: (0.5, 0.8, 0.0, 0.9),  # ankle
    })

    angle = joint_angle(frame, 23, 25, 27)

    assert angle == pytest.approx(180.0, abs=2.0)


def test_joint_angle_visibilidade_baixa_devolve_none():
    """Landmark com visibilidade < 0.5 → None."""
    frame = _make_full_frame({
        23: (0.5, 0.4, 0.0, 0.9),   # OK
        25: (0.5, 0.6, 0.0, 0.3),   # visibility too low
        27: (0.3, 0.6, 0.0, 0.9),   # OK
    })

    angle = joint_angle(frame, 23, 25, 27)

    assert angle is None


# --------------------------------------------------------------------------- #
# trunk_tilt
# --------------------------------------------------------------------------- #
def test_trunk_tilt_vertical():
    """Espinha perfeitamente vertical → ângulo ~0°."""
    frame = _make_full_frame({
        11: (0.50, 0.20, 0.0, 0.9),  # shoulder L
        12: (0.50, 0.20, 0.0, 0.9),  # shoulder R
        23: (0.50, 0.60, 0.0, 0.9),  # hip L
        24: (0.50, 0.60, 0.0, 0.9),  # hip R
    })

    tilt = trunk_tilt(frame)

    assert tilt == pytest.approx(0.0, abs=1.0)


def test_trunk_tilt_30_graus():
    """Espinha inclinada ~26.6° (dx=0.2, dy=0.4 → arctan(0.2/0.4) ≈ 26.6°)."""
    import math

    # Ombros deslocados 0.2 em X relativamente aos quadris (dy=0.4 de distância)
    dx = 0.2

    frame = _make_full_frame({
        11: (0.50 + dx, 0.20, 0.0, 0.9),
        12: (0.50 + dx, 0.20, 0.0, 0.9),
        23: (0.50, 0.60, 0.0, 0.9),
        24: (0.50, 0.60, 0.0, 0.9),
    })

    tilt = trunk_tilt(frame)

    # arctan(0.2/0.4) = arctan(0.5) ≈ 26.57°
    expected = math.degrees(math.atan(0.2 / 0.4))
    assert tilt == pytest.approx(expected, abs=1.0)


def test_trunk_tilt_visibilidade_baixa_devolve_none():
    """Visibilidade < 0.5 em ombro → None."""
    frame = _make_full_frame({
        11: (0.50, 0.20, 0.0, 0.3),  # visibility too low
        12: (0.50, 0.20, 0.0, 0.9),
        23: (0.50, 0.60, 0.0, 0.9),
        24: (0.50, 0.60, 0.0, 0.9),
    })

    tilt = trunk_tilt(frame)

    assert tilt is None


# --------------------------------------------------------------------------- #
# joint_angles_per_frame
# --------------------------------------------------------------------------- #
def test_joint_angles_per_frame_multi_joint():
    """Vários ângulos num frame → dicionário com nome → ângulo."""
    frame = _make_full_frame({
        23: (0.5, 0.4, 0.0, 0.9),   # hip L
        25: (0.5, 0.6, 0.0, 0.9),   # knee L
        27: (0.3, 0.6, 0.0, 0.9),   # ankle L
        24: (0.5, 0.4, 0.0, 0.9),   # hip R
        26: (0.5, 0.6, 0.0, 0.9),   # knee R
        28: (0.7, 0.6, 0.0, 0.9),   # ankle R
    })

    joints = [
        ("knee_left", 23, 25, 27),
        ("knee_right", 24, 26, 28),
    ]
    angles = joint_angles_per_frame(frame, joints)

    assert "knee_left" in angles
    assert "knee_right" in angles
    assert angles["knee_left"] == pytest.approx(90.0, abs=1.0)
    assert angles["knee_right"] == pytest.approx(90.0, abs=1.0)


# --------------------------------------------------------------------------- #
# select_ground_person
# --------------------------------------------------------------------------- #
def test_select_ground_person_single_person():
    """Com uma única pessoa em ≥3 frames consecutivos → devolve essa pessoa."""
    frame = _make_full_frame()
    # Precisa de 3+ frames consecutivos para passar no filtro temporal
    all_poses = [[frame], [frame], [frame], [frame]]

    result, track_ids = select_ground_person(all_poses)

    assert len(result) == 4
    assert all(r is not None for r in result)
    assert result[0] == frame
    assert len(track_ids) == 4
    # Sem tracking ativo, track_ids são None
    assert all(t is None for t in track_ids)


def test_select_ground_person_picks_lowest_y():
    """Pessoa com Y maior (mais abaixo na imagem) deve ser selecionada."""
    floor_landmarks = [(0.5, 0.9, 0.0, 0.9) for _ in range(33)]
    stand_landmarks = [(0.5, 0.3, 0.0, 0.9) for _ in range(33)]
    person_floor = PoseFrame(landmarks=floor_landmarks)
    person_stand = PoseFrame(landmarks=stand_landmarks)

    # 4 frames consecutivos com 2 pessoas
    all_poses = [[person_stand, person_floor]] * 4

    result, track_ids = select_ground_person(all_poses)

    assert len(result) == 4
    assert result[0] is not None
    avg_y = sum(lm[1] for lm in result[0].landmarks) / 33
    assert avg_y == pytest.approx(0.9, abs=0.01)


def test_select_ground_person_all_none():
    """Frame sem nenhuma pessoa → None."""
    all_poses = [[None, None]] * 4

    result, track_ids = select_ground_person(all_poses)

    assert result == [None, None, None, None]
    assert track_ids == [None, None, None, None]


def test_select_ground_person_mixed_frames():
    """Alguns frames com pessoa, outros sem — streak de 3+ mantém a pessoa."""
    frame_a = _make_full_frame()
    all_poses = [[frame_a], [frame_a], [frame_a], [None], [frame_a], [frame_a], [frame_a]]

    result, track_ids = select_ground_person(all_poses)

    assert len(result) == 7
    assert result[0] is not None
    assert result[1] is not None
    assert result[2] is not None
    assert result[3] is None  # frame vazio
    assert result[4] is not None  # streak de 3 retoma
    assert result[5] is not None
    assert result[6] is not None


def test_select_ground_person_sporadic_ignored():
    """Deteção esporádica (< 2 frames consecutivos) → ignorada (ITER2-08)."""
    frame = _make_full_frame()
    # Apenas 1 frame isolado — não atinge o mínimo de 2 consecutivos
    all_poses = [[frame], [None], [None], [None], [None]]

    result, track_ids = select_ground_person(all_poses)

    assert result == [None, None, None, None, None]


# --------------------------------------------------------------------------- #
# vertical_velocity / max_vertical_velocity
# --------------------------------------------------------------------------- #
def test_vertical_velocity_queda_produz_pico_positivo():
    """Queda real: quadril desce → Vy positivo (eixo Y invertido no MediaPipe)."""
    # Frame 1: quadril em y=0.4 (alto), frame 2: y=0.8 (baixo) → Vy = +0.4
    f1 = _make_full_frame({23: (0.50, 0.40, 0.0, 0.9), 24: (0.52, 0.40, 0.0, 0.9)})
    f2 = _make_full_frame({23: (0.50, 0.80, 0.0, 0.9), 24: (0.52, 0.80, 0.0, 0.9)})

    vy = vertical_velocity([f1, f2])

    assert len(vy) == 2
    assert vy[0] is None  # primeiro frame sem referência
    assert vy[1] == pytest.approx(0.40, abs=0.01)


def test_vertical_velocity_estatico_produz_zero():
    """Pessoa parada → Vy ≈ 0."""
    f = _make_full_frame({23: (0.50, 0.50, 0.0, 0.9), 24: (0.52, 0.50, 0.0, 0.9)})
    vy = vertical_velocity([f, f, f])

    assert vy[1] == pytest.approx(0.0, abs=0.01)
    assert vy[2] == pytest.approx(0.0, abs=0.01)


def test_max_vertical_velocity_pico_isolado_aceito():
    """1 frame >0.08 já é suficiente (CCTV/15fps compat)."""
    vy = [0.0, 0.0, 0.25, 0.0, 0.0, 0.0]
    max_v = max_vertical_velocity(vy, window_frames=6)
    assert max_v == pytest.approx(0.25, abs=0.01)


def test_max_vertical_velocity_abaixo_do_piso_ignorado():
    """Nenhum frame >0.08 → 0.0."""
    vy = [0.0, 0.07, 0.05, 0.0, 0.0]
    max_v = max_vertical_velocity(vy, window_frames=5)
    assert max_v == 0.0


def test_max_vertical_velocity_ignora_none():
    """Frames None são ignorados."""
    vy = [None, 0.3, None, 0.1, None]
    max_v = max_vertical_velocity(vy, window_frames=5)
    assert max_v == pytest.approx(0.3, abs=0.01)


# --------------------------------------------------------------------------- #
# total_displacement
# --------------------------------------------------------------------------- #
def test_total_displacement_acumula_descidas():
    """Soma todos os Vy positivos."""
    vy = [0.05, 0.10, -0.02, 0.08, None]
    td = total_displacement(vy)
    assert td == pytest.approx(0.23, abs=0.01)


def test_total_displacement_sem_descida():
    """Sem Vy positivo → 0.0."""
    vy = [-0.01, -0.02, 0.0, None]
    td = total_displacement(vy)
    assert td == 0.0


def test_total_displacement_vazio():
    """Lista vazia → 0.0."""
    assert total_displacement([]) == 0.0


def test_max_vertical_velocity_empty():
    """Sem dados → 0.0."""
    assert max_vertical_velocity([], window_frames=15) == 0.0
    assert max_vertical_velocity([None, None], window_frames=15) == 0.0


# --------------------------------------------------------------------------- #
# is_recumbent — detecção de posição deitada com janela deslizante
# --------------------------------------------------------------------------- #
def test_is_recumbent_person_lying_down():
    """Pessoa com Y>0.45 consistente → True."""
    from pipelines.video.pose_features import is_recumbent

    # 100 frames com quadril em Y=0.8 (deitado)
    frames = [
        _make_full_frame({23: (0.50, 0.80, 0.0, 0.9), 24: (0.52, 0.80, 0.0, 0.9)})
        for _ in range(100)
    ]
    assert is_recumbent(frames) is True


def test_is_recumbent_person_standing():
    """Pessoa com Y<0.45 consistente → False."""
    from pipelines.video.pose_features import is_recumbent

    frames = [
        _make_full_frame({23: (0.50, 0.30, 0.0, 0.9), 24: (0.52, 0.30, 0.0, 0.9)})
        for _ in range(100)
    ]
    assert is_recumbent(frames) is False


def test_is_recumbent_insufficient_data():
    """Menos de 10 frames válidos → False (dados insuficientes)."""
    from pipelines.video.pose_features import is_recumbent

    # Apenas 5 frames — abaixo do mínimo de 10
    frames = [
        _make_full_frame({23: (0.50, 0.80, 0.0, 0.9), 24: (0.52, 0.80, 0.0, 0.9)})
        for _ in range(5)
    ]
    assert is_recumbent(frames) is False


def test_is_recumbent_transition_from_lying_to_standing():
    """Transição deitado→em pé: is_recumbent segue a janela deslizante."""
    from pipelines.video.pose_features import is_recumbent

    # 100 frames deitado + 100 frames em pé
    lying = [
        _make_full_frame({23: (0.50, 0.80, 0.0, 0.9), 24: (0.52, 0.80, 0.0, 0.9)})
        for _ in range(100)
    ]
    standing = [
        _make_full_frame({23: (0.50, 0.30, 0.0, 0.9), 24: (0.52, 0.30, 0.0, 0.9)})
        for _ in range(100)
    ]

    # Após 100 frames deitado → True
    assert is_recumbent(lying) is True

    # Após transição: 100 deitado + 50 em pé → últimos 90 frames: 40 deitado + 50 em pé
    # Y médio ≈ (40*0.80 + 50*0.30)/90 ≈ 0.522 → >0.45 → ainda True
    mixed_150 = lying + standing[:50]
    assert is_recumbent(mixed_150) is True

    # Após 100 deitado + 100 em pé → últimos 90 frames: 90 em pé → Y≈0.30 → False
    mixed_200 = lying + standing
    assert is_recumbent(mixed_200) is False


def test_is_recumbent_handles_none_frames():
    """Frames None são ignorados na janela deslizante."""
    from pipelines.video.pose_features import is_recumbent

    valid = _make_full_frame({23: (0.50, 0.80, 0.0, 0.9), 24: (0.52, 0.80, 0.0, 0.9)})
    # 90 frames válidos + 30 None intercalados
    frames = [valid, None] * 45 + [valid] * 30
    assert is_recumbent(frames) is True


def test_is_recumbent_uses_fallback_when_hips_occluded():
    """Quando quadris têm baixa visibilidade, usa upper_body_center como fallback."""
    from pipelines.video.pose_features import is_recumbent

    # Quadril com visibilidade < 0.5, mas parte superior visível
    frames = []
    for _ in range(100):
        f = _make_full_frame({
            23: (0.50, 0.80, 0.0, 0.3),  # quadril ocluído
            24: (0.52, 0.80, 0.0, 0.3),  # quadril ocluído
            0: (0.50, 0.70, 0.0, 0.9),   # nariz visível
            11: (0.50, 0.75, 0.0, 0.9),  # ombro esquerdo visível
            12: (0.52, 0.75, 0.0, 0.9),  # ombro direito visível
        })
        frames.append(f)
    # Upper body Y ≈ (0.70+0.75+0.75)/3 ≈ 0.733 > 0.45 → True
    assert is_recumbent(frames) is True


# --------------------------------------------------------------------------- #
# group_poses_by_track_id — agrupamento de poses por identidade
# --------------------------------------------------------------------------- #
def test_group_poses_by_track_id_two_consistent_people():
    """2 pessoas com track_ids estáveis → 2 timelines completas."""
    from pipelines.video.pose_features import group_poses_by_track_id

    p0 = _make_full_frame()
    p0 = PoseFrame(landmarks=p0.landmarks, track_id=0)
    p1 = _make_full_frame()
    p1 = PoseFrame(landmarks=p1.landmarks, track_id=1)

    all_poses = [[p0, p1], [p0, p1], [p0, p1], [p0, p1]]
    result = group_poses_by_track_id(all_poses)

    assert len(result) == 2
    assert 0 in result
    assert 1 in result
    assert len(result[0]) == 4
    assert len(result[1]) == 4
    assert result[0][0] == p0
    assert result[1][0] == p1


def test_group_poses_by_track_id_swapped_order():
    """Ordem dos índices troca entre frames — agrupamento por track_id é imune."""
    from pipelines.video.pose_features import group_poses_by_track_id

    p0 = _make_full_frame()
    p0 = PoseFrame(landmarks=p0.landmarks, track_id=0)
    p1 = _make_full_frame()
    p1 = PoseFrame(landmarks=p1.landmarks, track_id=1)

    # Frame 0: [p0, p1]; Frame 1: [p1, p0] — índices trocados
    all_poses = [[p0, p1], [p1, p0], [p0, p1], [p1, p0]]
    result = group_poses_by_track_id(all_poses)

    assert len(result) == 2
    # Cada track_id deve ter 4 frames, independente da ordem
    assert len(result[0]) == 4
    assert len(result[1]) == 4
    # track_id 0 está presente nos 4 frames
    assert all(r is not None for r in result[0])


def test_group_poses_by_track_id_none_track_id_excluded():
    """Poses sem track_id (None) são excluídas do agrupamento."""
    from pipelines.video.pose_features import group_poses_by_track_id

    p_tracked = _make_full_frame()
    p_tracked = PoseFrame(landmarks=p_tracked.landmarks, track_id=5)
    p_untracked = _make_full_frame()  # track_id=None

    all_poses = [[p_tracked, p_untracked], [p_tracked, p_untracked]]
    result = group_poses_by_track_id(all_poses)

    # Só o track_id=5 deve aparecer; untracked é ignorado
    assert 5 in result
    assert None not in result
    assert len(result) == 1


def test_group_poses_by_track_id_gaps_filled_with_none():
    """track_id ausente em alguns frames → posição preenchida com None."""
    from pipelines.video.pose_features import group_poses_by_track_id

    p0 = _make_full_frame()
    p0 = PoseFrame(landmarks=p0.landmarks, track_id=0)

    # track_id=0 aparece só nos frames 0 e 2
    all_poses = [[p0], [], [p0], []]
    result = group_poses_by_track_id(all_poses)

    assert len(result) == 1
    assert 0 in result
    assert result[0][0] == p0
    assert result[0][1] is None  # gap preenchido
    assert result[0][2] == p0
    assert result[0][3] is None  # gap preenchido


def test_group_poses_by_track_id_empty_input():
    """Input vazio → dicionário vazio."""
    from pipelines.video.pose_features import group_poses_by_track_id

    assert group_poses_by_track_id([]) == {}
    assert group_poses_by_track_id([[], [], []]) == {}


# --------------------------------------------------------------------------- #
# T1: Unified visibility threshold (0.4) + reduced streak minimum (2)
# --------------------------------------------------------------------------- #
def test_hip_center_returns_coords_at_visibility_045():
    """Visibilidade 0.45 → hip_center devolve coordenadas (threshold 0.4)."""
    from pipelines.video.pose_features import hip_center

    frame = _make_full_frame({
        23: (0.50, 0.60, 0.0, 0.45),  # hip L — antes era < 0.5, agora > 0.4
        24: (0.52, 0.60, 0.0, 0.45),  # hip R
    })

    result = hip_center(frame)
    assert result is not None
    assert result[0] == pytest.approx(0.51, abs=0.01)
    assert result[1] == pytest.approx(0.60, abs=0.01)


def test_hip_center_still_none_below_04():
    """Visibilidade < 0.4 → hip_center continua a devolver None."""
    from pipelines.video.pose_features import hip_center

    frame = _make_full_frame({
        23: (0.50, 0.60, 0.0, 0.3),  # abaixo do novo threshold
        24: (0.52, 0.60, 0.0, 0.9),
    })

    result = hip_center(frame)
    assert result is None


def test_select_ground_person_two_consecutive_frames_included():
    """Pessoa em 2 frames consecutivos → incluída (streak mínimo = 2)."""
    from pipelines.video.pose_features import select_ground_person

    frame = _make_full_frame()
    # Apenas 2 frames consecutivos — antes era descartado (< 3), agora incluído (≥ 2)
    all_poses = [[frame], [frame], [], [], []]

    result, track_ids = select_ground_person(all_poses)

    assert result[0] is not None
    assert result[1] is not None


def test_select_ground_person_single_isolated_frame_excluded():
    """Pessoa em apenas 1 frame isolado → descartada (ruído)."""
    from pipelines.video.pose_features import select_ground_person

    frame = _make_full_frame()
    all_poses = [[frame], [], [], [], []]

    result, track_ids = select_ground_person(all_poses)

    assert result == [None, None, None, None, None]
