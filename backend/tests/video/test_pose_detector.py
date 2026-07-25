"""Testes de `pose_detector.py`."""

import json
from pathlib import Path

import pytest

from pipelines.video.models import JointTarget, MovementWindow, PoseFrame, PosturalFinding
from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_keypoints
from pipelines.video.pose_detector import (
    classify_sequence,
    classify_with_persistence,
    detect_postural_deviations,
    detect_trunk_tilt,
    save_fall_evidence,
    save_postural_evidence,
)

_URFD_FRAME = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "urfd"
    / "fall-01"
    / "fall-01-cam0-rgb"
    / "fall-01-cam0-rgb-050.png"
)


def _window(amplitude: float, start: int = 0, end: int = 9) -> MovementWindow:
    return MovementWindow(
        start_frame=start,
        end_frame=end,
        center_of_mass_amplitude=amplitude,
        velocity=0.0,
        asymmetry=0.0,
    )


def test_classifica_queda_quando_alguma_janela_excede_o_limiar():
    windows = [_window(0.05), _window(0.6), _window(0.02)]

    assert classify_sequence(windows, threshold=0.3) == "queda"


def test_classifica_adl_quando_nenhuma_janela_excede_o_limiar():
    windows = [_window(0.05), _window(0.1), _window(0.02)]

    assert classify_sequence(windows, threshold=0.3) == "adl"


def test_classifica_dados_insuficientes_quando_nao_ha_janelas():
    assert classify_sequence([], threshold=0.3) == "dados_insuficientes"


def test_limiar_e_estritamente_excedido_nao_apenas_igualado():
    # Amplitude exatamente igual ao limiar não deve contar como "queda" --
    # discrimina de um `>=` (implementação errada plausível) de um `>`.
    windows = [_window(0.3)]

    assert classify_sequence(windows, threshold=0.3) == "adl"


@pytest.fixture(scope="module")
def landmarker(tmp_path_factory):
    cache_dir = tmp_path_factory.mktemp("pose_model_cache_detector")
    model_path = ensure_pose_model(cache_dir)
    return create_landmarker(model_path)


def test_save_fall_evidence_gera_artefato_real_e_sidecar_no_disco(tmp_path, landmarker):
    pose_frame = extract_keypoints(_URFD_FRAME, landmarker)
    assert pose_frame is not None  # pré-condição do teste: frame real com pessoa detectável

    evidence = save_fall_evidence(
        seq_id="fall-01",
        frame_path=_URFD_FRAME,
        pose_frame=pose_frame,
        event_frame_index=50,
        score=0.87,
        run_id="run-teste",
        root=tmp_path,
    )

    assert evidence.artifact_path.is_file()
    assert evidence.sidecar_path.is_file()

    sidecar = json.loads(evidence.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["seq_id"] == "fall-01"
    assert sidecar["metadata"]["event_frame"] == 50
    assert sidecar["metadata"]["score"] == 0.87


# --------------------------------------------------------------------------- #
# classify_with_persistence — filtro temporal
# --------------------------------------------------------------------------- #
def test_persistence_all_above_threshold_confirms_fall():
    """30 janelas todas acima do limiar → queda confirmada."""
    windows = [_window(0.7, start=i * 10, end=i * 10 + 9) for i in range(30)]

    verdict, frame_idx = classify_with_persistence(windows, 0.55, persistence_frames=30)

    assert verdict == "queda"
    assert frame_idx == 0  # first window of the streak


def test_persistence_counter_resets_on_below_threshold():
    """20 acima, 1 abaixo, depois 40 acima → reset, queda no segundo streak."""
    windows = (
        [_window(0.7) for _ in range(20)]
        + [_window(0.3)]  # reset!
        + [_window(0.7, start=22, end=31) for _ in range(40)]
    )

    verdict, frame_idx = classify_with_persistence(windows, 0.55, persistence_frames=30)

    assert verdict == "queda"
    assert frame_idx == 22  # start of second streak


def test_persistence_all_below_threshold_no_fall():
    """Todas as janelas abaixo do limiar → adl."""
    windows = [_window(0.1) for _ in range(50)]

    verdict, frame_idx = classify_with_persistence(windows, 0.55, persistence_frames=30)

    assert verdict == "adl"
    assert frame_idx is None


def test_persistence_agachamento_nao_dispara():
    """Amplitude 0.50 com threshold 0.55 → não é queda (filtra agachamento)."""
    windows = [_window(0.50) for _ in range(60)]

    verdict, frame_idx = classify_with_persistence(windows, 0.55, persistence_frames=30)

    assert verdict == "adl"


def test_persistence_empty_windows():
    """Lista vazia → dados insuficientes."""
    verdict, frame_idx = classify_with_persistence([], 0.55, persistence_frames=30)

    assert verdict == "dados_insuficientes"
    assert frame_idx is None


def test_persistence_exactly_at_threshold_no_fall():
    """Amplitude igual ao limiar não dispara queda (comportamento >, não >=)."""
    windows = [_window(0.55) for _ in range(60)]

    verdict, frame_idx = classify_with_persistence(windows, 0.55, persistence_frames=30)

    assert verdict == "adl"


def test_classify_sequence_unchanged_backward_compat():
    """classify_sequence original deve continuar a funcionar."""
    windows = [_window(0.6)]

    assert classify_sequence(windows, threshold=0.3) == "queda"
    assert classify_sequence([_window(0.1)], threshold=0.3) == "adl"
    assert classify_sequence([], threshold=0.3) == "dados_insuficientes"


# --------------------------------------------------------------------------- #
# detect_postural_deviations
# --------------------------------------------------------------------------- #
def _make_joint_frame(
    hip_xy: tuple[float, float],
    knee_xy: tuple[float, float],
    ankle_xy: tuple[float, float],
) -> PoseFrame:
    """Frame sintético com landmarks de perna esquerda (23, 25, 27) configuráveis."""
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    landmarks[23] = (*hip_xy, 0.0, 0.9)
    landmarks[25] = (*knee_xy, 0.0, 0.9)
    landmarks[27] = (*ankle_xy, 0.0, 0.9)
    return PoseFrame(landmarks=landmarks)


def test_postural_deviation_detected_after_persistence():
    """40 frames com joelho a ~69° (min=70) → 1 finding emitido."""
    joint_targets = [
        JointTarget("knee_left", 23, 25, 27, min_angle=70.0, target_angle=90.0),
    ]
    # Joelho a ~90° (OK) nos primeiros 5 frames, depois ~69° por 40 frames
    # Ângulo ~69°: ankle a (0.94, 0.43) com knee a (0.5, 0.6) e hip a (0.5, 0.4)
    good = _make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.3, 0.6))        # ~90°
    bad = _make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.94, 0.43))       # ~69°
    frames = [good for _ in range(5)] + [bad for _ in range(40)]

    findings = detect_postural_deviations(frames, joint_targets, persistence_frames=30, fps=30.0)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "POSTURAL_DEVIATION"
    assert f.joint_name == "knee_left"
    assert f.duration_s == pytest.approx(1.0, abs=0.2)
    assert "69" in f.description or "joelho" in f.description.lower()
    assert 0.0 <= f.score <= 1.0


def test_postural_deviation_counter_resets_when_angle_recovers():
    """20 frames ruins, 1 frame OK, depois 40 ruins → reset, só o segundo streak gera finding."""
    joint_targets = [
        JointTarget("knee_left", 23, 25, 27, min_angle=70.0, target_angle=90.0),
    ]
    bad = _make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.94, 0.43))   # ~69°
    good = _make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.3, 0.6))     # ~90°

    frames = [bad for _ in range(20)] + [good] + [bad for _ in range(40)]

    findings = detect_postural_deviations(frames, joint_targets, persistence_frames=30, fps=30.0)

    assert len(findings) == 1  # só o segundo streak


def test_postural_deviation_all_good_no_findings():
    """Todos os frames acima do mínimo → sem findings."""
    joint_targets = [
        JointTarget("knee_left", 23, 25, 27, min_angle=70.0, target_angle=90.0),
    ]
    frames = [_make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.3, 0.6)) for _ in range(50)]

    findings = detect_postural_deviations(frames, joint_targets, persistence_frames=30, fps=30.0)

    assert findings == []


def test_postural_deviation_none_frame_resets_counter():
    """Frame None no meio de uma streak → counter reseta."""
    joint_targets = [
        JointTarget("knee_left", 23, 25, 27, min_angle=70.0, target_angle=90.0),
    ]
    bad = _make_joint_frame((0.5, 0.4), (0.5, 0.6), (0.94, 0.43))

    frames = [bad for _ in range(20)] + [None] + [bad for _ in range(20)]

    findings = detect_postural_deviations(frames, joint_targets, persistence_frames=30, fps=30.0)

    assert findings == []  # nenhum streak atinge 30 frames consecutivos


# --------------------------------------------------------------------------- #
# detect_trunk_tilt
# --------------------------------------------------------------------------- #
def _make_tilt_frame(shoulder_y: float, hip_y: float, dx: float) -> PoseFrame:
    """Frame com posição de ombros e quadris controlada para teste de tilt."""
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    landmarks[11] = (0.50 + dx, shoulder_y, 0.0, 0.9)  # shoulder L
    landmarks[12] = (0.50 + dx, shoulder_y, 0.0, 0.9)  # shoulder R
    landmarks[23] = (0.50, hip_y, 0.0, 0.9)              # hip L
    landmarks[24] = (0.50, hip_y, 0.0, 0.9)              # hip R
    return PoseFrame(landmarks=landmarks)


def test_trunk_tilt_detected_after_persistence():
    """100 frames com tilt de ~34° (max=30) → 1 finding."""
    # dx=0.2, dy=0.4 → arctan(0.2/0.4) ≈ 26.6°, queremos >30°: dx=0.25, dy=0.4 → 32°
    tilted = _make_tilt_frame(shoulder_y=0.20, hip_y=0.60, dx=0.25)
    frames = [tilted for _ in range(100)]

    findings = detect_trunk_tilt(frames, max_angle=30.0, persistence_frames=90, fps=30.0)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "TRUNK_TILT"
    assert f.joint_name is None
    assert f.measured_angle > 30.0
    assert f.duration_s == pytest.approx(3.0, abs=0.5)
    assert 0.0 <= f.score <= 1.0
    assert "inclinação" in f.description.lower()


def test_trunk_tilt_below_threshold_no_finding():
    """Tilt < 30° → sem findings."""
    # dx=0.1, dy=0.4 → arctan(0.1/0.4) ≈ 14°
    straight = _make_tilt_frame(shoulder_y=0.20, hip_y=0.60, dx=0.1)
    frames = [straight for _ in range(100)]

    findings = detect_trunk_tilt(frames, max_angle=30.0, persistence_frames=90, fps=30.0)

    assert findings == []


def test_trunk_tilt_counter_resets_on_recovery():
    """50 frames tilt, 1 straight, 95 tilt → reset, só o segundo streak."""
    tilted = _make_tilt_frame(shoulder_y=0.20, hip_y=0.60, dx=0.25)
    straight = _make_tilt_frame(shoulder_y=0.20, hip_y=0.60, dx=0.0)

    frames = [tilted for _ in range(50)] + [straight] + [tilted for _ in range(95)]

    findings = detect_trunk_tilt(frames, max_angle=30.0, persistence_frames=90, fps=30.0)

    assert len(findings) == 1  # só o segundo streak


def test_trunk_tilt_none_frame_resets_counter():
    """Frame None no meio da streak → reseta."""
    tilted = _make_tilt_frame(shoulder_y=0.20, hip_y=0.60, dx=0.25)

    frames = [tilted for _ in range(50)] + [None] + [tilted for _ in range(50)]

    findings = detect_trunk_tilt(frames, max_angle=30.0, persistence_frames=90, fps=30.0)

    assert findings == []  # nenhum streak atinge 90 frames


# --------------------------------------------------------------------------- #
# save_postural_evidence + save_fall_evidence metadata expandido
# --------------------------------------------------------------------------- #
def test_save_fall_evidence_metadata_expandido(tmp_path, landmarker):
    """save_fall_evidence agora inclui finding_type e persistence_frames."""
    pose_frame = extract_keypoints(_URFD_FRAME, landmarker)
    assert pose_frame is not None

    evidence = save_fall_evidence(
        seq_id="fall-01",
        frame_path=_URFD_FRAME,
        pose_frame=pose_frame,
        event_frame_index=50,
        score=0.87,
        run_id="run-teste",
        root=tmp_path,
        persistence_frames=32,
    )

    sidecar = json.loads(evidence.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["finding_type"] == "FALL_DETECTED"
    assert sidecar["metadata"]["persistence_frames"] == 32
    assert "description" in sidecar["metadata"]


def test_save_postural_evidence_produz_sidecar(tmp_path, landmarker):
    """save_postural_evidence grava artefato + sidecar com metadados clínicos."""
    pose_frame = extract_keypoints(_URFD_FRAME, landmarker)
    assert pose_frame is not None

    finding = PosturalFinding(
        finding_type="POSTURAL_DEVIATION",
        joint_name="knee_left",
        measured_angle=62.0,
        expected_angle=70.0,
        duration_s=1.5,
        frame_index=95,
        score=0.42,
        description="Amplitude reduzida (62°, esperado >70°).",
    )

    evidence = save_postural_evidence(
        finding=finding,
        frame_path=_URFD_FRAME,
        pose_frame=pose_frame,
        run_id="run-teste",
        root=tmp_path,
    )

    assert evidence.artifact_path.is_file()
    assert evidence.sidecar_path.is_file()
    sidecar = json.loads(evidence.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["finding_type"] == "POSTURAL_DEVIATION"
    assert sidecar["metadata"]["joint_name"] == "knee_left"
    assert sidecar["metadata"]["measured_angle"] == 62.0
    assert sidecar["metadata"]["duration_s"] == 1.5


def test_save_postural_evidence_trunk_tilt(tmp_path, landmarker):
    """save_postural_evidence para TRUNK_TILT — joint_name=None, ângulo presente."""
    pose_frame = extract_keypoints(_URFD_FRAME, landmarker)
    assert pose_frame is not None

    finding = PosturalFinding(
        finding_type="TRUNK_TILT",
        joint_name=None,
        measured_angle=34.0,
        expected_angle=30.0,
        duration_s=4.2,
        frame_index=120,
        score=0.57,
        description="Inclinação de tronco (34° por 4.2s).",
    )

    evidence = save_postural_evidence(
        finding=finding,
        frame_path=_URFD_FRAME,
        pose_frame=pose_frame,
        run_id="run-teste",
        root=tmp_path,
    )

    sidecar = json.loads(evidence.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["finding_type"] == "TRUNK_TILT"
    assert sidecar["metadata"]["joint_name"] is None
    assert sidecar["metadata"]["measured_angle"] == 34.0
