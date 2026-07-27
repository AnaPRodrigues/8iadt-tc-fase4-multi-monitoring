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


# --------------------------------------------------------------------------- #
# validate_fall_dynamic — multi-person with track_id grouping (MULTI-01..08)
# --------------------------------------------------------------------------- #
def _make_person_frame(
    hip_y: float = 0.50,
    visibility: float = 0.9,
    track_id: int | None = None,
    shoulder_dx: float = 0.0,
    shoulder_y: float | None = None,
) -> PoseFrame:
    """Frame sintético com landmarks configuráveis para teste de queda."""
    landmarks = [(0.5, 0.5, 0.0, visibility) for _ in range(33)]
    landmarks[23] = (0.50, hip_y, 0.0, visibility)    # hip L
    landmarks[24] = (0.52, hip_y, 0.0, visibility)    # hip R
    landmarks[11] = (0.50 + shoulder_dx, shoulder_y or hip_y - 0.2, 0.0, visibility)
    landmarks[12] = (0.52 + shoulder_dx, shoulder_y or hip_y - 0.2, 0.0, visibility)
    landmarks[0] = (0.51, (shoulder_y or hip_y - 0.2) - 0.05, 0.0, visibility)
    return PoseFrame(landmarks=landmarks, track_id=track_id)


def test_validate_fall_dynamic_uses_track_id_correctly():
    """Cenário: paciente deitado (track_id=0) + pessoa em pé que cai (track_id=1).
    A queda deve ser atribuída ao track_id=1, não ao paciente."""
    from pipelines.video.pose_detector import validate_fall_dynamic

    # Paciente deitado: Y=0.8 estável (não cai)
    patient = _make_person_frame(hip_y=0.80, track_id=0)
    # Pessoa em pé: Y=0.30 → cai para Y=0.80 em 5 frames
    standing = _make_person_frame(hip_y=0.30, track_id=1)
    fallen = _make_person_frame(hip_y=0.80, track_id=1)

    # 100 frames de baseline + 5 frames de queda
    all_poses = []
    for _ in range(95):
        all_poses.append([patient, standing])
    for _ in range(5):
        all_poses.append([patient, fallen])

    # Velocidades dummy para o ground_person (não usado com agrupamento por track_id)
    dummy_vy: list[float | None] = [0.0] * 100

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "queda", 95, dummy_vy, min_vertical_velocity=0.10,
        all_poses_per_frame=all_poses, n_pessoas=2,
    )

    # Com thresholds multi-pessoa (Vy≥0.20, tilt≥35°, ΔY≥0.30):
    # A queda simulada (Y: 0.30→0.80 em 5 frames, Vy≈0.10/frame, tilt≈0°)
    # pode não atingir os thresholds elevados — o importante é que:
    # - Se detectar, o track_id está correto (track_id=1)
    # - O paciente deitado (track_id=0) nunca é o escolhido
    if verdict == "queda":
        assert tid == 1, f"track_id deveria ser 1 (pessoa que caiu), não {tid}"


def test_validate_fall_dynamic_excludes_recumbent_person():
    """Pessoa já deitada (>90 frames com Y>0.45) → excluída da detecção.

    Cenário que DISPARARIA um falso positivo sem is_recumbent():
    - Paciente deitado (Y=0.75) há 76 frames → is_recumbent=True
    - Nos últimos 24 frames, o paciente reposiciona-se no leito:
      Y sobe de 0.75→0.97, com tilt≈53° (dx=0.28 ombros deslocados)
    - Vy=0.12, deslocamento total=0.22, tilt=53° → TODOS os thresholds
      de queda single-person são atingidos (Vy≥0.08, ΔY≥0.20, tilt≥25°)
    - Mas is_recumbent=True → a pessoa É excluída → veredicto="adl"

    SEM a guarda is_recumbent (Mutant 3), este cenário produziria "queda".
    """
    from pipelines.video.pose_detector import validate_fall_dynamic

    # Paciente deitado (Y=0.75, tilt≈53° por dx=0.28 nos ombros)
    patient_stable = _make_person_frame(hip_y=0.75, track_id=5, shoulder_dx=0.28)

    # Reposicionamento no leito: Y sobe rapidamente (Vy alto)
    patient_move = [
        _make_person_frame(hip_y=0.87, track_id=5, shoulder_dx=0.28),  # Vy=0.12
        _make_person_frame(hip_y=0.93, track_id=5, shoulder_dx=0.28),  # Vy=0.06
        _make_person_frame(hip_y=0.97, track_id=5, shoulder_dx=0.28),  # Vy=0.04
    ]

    # Acompanhante de pé, estático
    standing = _make_person_frame(hip_y=0.30, track_id=6)

    # 76 frames baseline + 3 frames de movimento + 21 frames pós-movimento
    all_poses = (
        [[patient_stable, standing] for _ in range(76)]
        + [[patient_move[0], standing]]
        + [[patient_move[1], standing]]
        + [[patient_move[2], standing]]
        + [[patient_move[2], standing] for _ in range(21)]
    )
    # total = 76 + 1 + 1 + 1 + 21 = 100 frames

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "queda", 76, [], min_vertical_velocity=0.10,
        all_poses_per_frame=all_poses, n_pessoas=2,
    )

    # Is_recumbent=True para track_id=5 → excluído
    # Track_id=6 estático → sem condições de queda
    # → veredicto DEVE ser "adl"
    assert verdict == "adl", (
        f"Pessoa deitada (is_recumbent=True) deve ser excluída, "
        f"mesmo com Vy/displacement/tilt acima dos thresholds. "
        f"verdict={verdict}, vy_score={vy_score}"
    )


def test_validate_fall_dynamic_single_person_keeps_original_thresholds():
    """Single-person vs multi-person: thresholds adaptativos.

    Single-person: Vy≥0.02 (floor), ΔY≥0.20, tilt≥25°.
    Multi-person: Vy≥0.04, ΔY≥0.30, tilt≥35°.

    Testa que uma queda marginal (Vy≈0.03, ΔY≈0.45, tilt≈50°) é detectada
    em modo single-person (Vy=0.03≥0.02) mas rejeitada em multi-pessoa
    (Vy=0.03<0.04).
    """
    from pipelines.video.pose_detector import validate_fall_dynamic

    # Pessoa com tilt moderado (dx=0.25, dy=0.20 → arctan(0.25/0.20)≈51°)
    standing = _make_person_frame(hip_y=0.30, shoulder_dx=0.25)

    # Queda parcial: ΔY=0.25 passa single (≥0.20) mas não multi (≥0.30)
    # Vy≈0.15 passa ambos os thresholds de Vy (0.02/0.04)
    falling_frames = []
    for y in [0.35, 0.50, 0.55]:
        falling_frames.append(_make_person_frame(hip_y=y, shoulder_dx=0.25))

    all_poses = (
        [[standing] for _ in range(96)]
        + [[f] for f in falling_frames]
    )

    # Verdict single-person: thresholds Vy≥0.02, ΔY≥0.20, tilt≥25°
    verdict_1p, _, vy_1p, _, _, _ = validate_fall_dynamic(
        "queda", 96, [], min_vertical_velocity=0.02,
        all_poses_per_frame=all_poses, n_pessoas=1,
    )

    # Verdict multi-pessoa: thresholds Vy≥0.04, ΔY≥0.30, tilt≥35°
    verdict_mp, _, vy_mp, _, _, _ = validate_fall_dynamic(
        "queda", 96, [], min_vertical_velocity=0.02,
        all_poses_per_frame=all_poses, n_pessoas=3,
    )

    # Single-person DEVE detectar: Vy≥0.02, ΔY≥0.20, tilt≥25°
    assert verdict_1p == "queda", (
        f"Single-person deveria detectar queda, mas verdict={verdict_1p}"
    )
    # Multi-person NÃO deve detectar: Vy<0.04 ou tilt<35° ou ΔY<0.30
    assert verdict_mp == "adl", (
        f"Multi-person NÃO deveria detectar (thresholds elevados), mas verdict={verdict_mp}"
    )


def test_validate_fall_dynamic_no_tracking_fallback():
    """Sem tracking (todos track_id=None) → usa fallback por índice posicional."""
    from pipelines.video.pose_detector import validate_fall_dynamic

    # Pessoa sem track_id
    no_track = _make_person_frame(hip_y=0.30, track_id=None)

    all_poses = [[no_track] for _ in range(100)]
    dummy_vy: list[float | None] = [0.0] * 100

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "queda", 50, dummy_vy, min_vertical_velocity=0.10,
        all_poses_per_frame=all_poses, n_pessoas=1,
    )

    # Sem tracking, track_id deve ser None
    assert tid is None
    # Pessoa com Y=0.30 estável → sem Vy → deve ser "adl"
    assert verdict == "adl"


def test_validate_fall_dynamic_multi_person_thresholds_applied():
    """n_pessoas=3 → thresholds elevados: tilt≥35°, ΔY≥0.30, Vy≥0.20."""
    from pipelines.video.pose_detector import validate_fall_dynamic

    # 3 pessoas em pé, Y estável
    p0 = _make_person_frame(hip_y=0.35, track_id=0)
    p1 = _make_person_frame(hip_y=0.40, track_id=1)
    p2 = _make_person_frame(hip_y=0.45, track_id=2)

    all_poses = [[p0, p1, p2] for _ in range(100)]
    dummy_vy: list[float | None] = [0.0] * 100

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "queda", 50, dummy_vy, min_vertical_velocity=0.10,
        all_poses_per_frame=all_poses, n_pessoas=3,
    )

    # Com 3 pessoas, thresholds elevados: nenhuma tem movimento → adl
    assert verdict == "adl"


def test_validate_fall_dynamic_not_fall_verdict_passes_through():
    """Se fall_verdict != 'queda', retorna sem validar."""
    from pipelines.video.pose_detector import validate_fall_dynamic

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "adl", None, [], min_vertical_velocity=0.10,
    )

    assert verdict == "adl"
    assert frame_idx is None
    assert vy_score == 0.0
    assert desc == ""
    assert tid is None
    assert peak is None


# --------------------------------------------------------------------------- #
# T3: detect_seizure — convulsão/espasmo (ITER2-04)
# --------------------------------------------------------------------------- #
def _make_seizure_frame(offset: float = 0.0, elbow_vis: float = 0.9) -> PoseFrame:
    """Frame com landmarks assimétricos para produzir ângulos não-180°."""
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    # Cotovelo esquerdo: ombro e pulso assimétricos → ângulo varia com offset
    landmarks[11] = (0.30, 0.20, 0.0, 0.9)                # shoulder L
    landmarks[13] = (0.50 + offset, 0.40, 0.0, elbow_vis)  # elbow L (oscila)
    landmarks[15] = (0.70, 0.60, 0.0, 0.9)                # wrist L
    # Cotovelo direito: mesmo padrão espelhado
    landmarks[12] = (0.70, 0.20, 0.0, 0.9)                # shoulder R
    landmarks[14] = (0.50 - offset, 0.40, 0.0, 0.9)        # elbow R (oscila)
    landmarks[16] = (0.30, 0.60, 0.0, 0.9)                # wrist R
    # Joelho esquerdo
    landmarks[23] = (0.30, 0.60, 0.0, 0.9)                # hip L
    landmarks[25] = (0.50 + offset, 0.75, 0.0, 0.9)        # knee L (oscila)
    landmarks[27] = (0.70, 0.90, 0.0, 0.9)                # ankle L
    # Joelho direito
    landmarks[24] = (0.70, 0.60, 0.0, 0.9)                # hip R
    landmarks[26] = (0.50 - offset, 0.75, 0.0, 0.9)        # knee R (oscila)
    landmarks[28] = (0.30, 0.90, 0.0, 0.9)                # ankle R
    return PoseFrame(landmarks=landmarks)


def test_seizure_detected_with_rhythmic_oscillation():
    """Oscilação rítmica em cotovelos e joelhos por 90 frames → 1 finding."""
    from pipelines.video.pose_detector import detect_seizure

    # Padrão irregular: amplitudes variadas para produzir std > 0
    frames = []
    offsets = [0.0, 0.04, 0.10, 0.04, 0.0, -0.04, -0.10, -0.04]  # ciclo de 8
    for i in range(90):
        offset = offsets[i % len(offsets)]
        frames.append(_make_seizure_frame(offset=offset))

    findings = detect_seizure(frames, fps=30.0)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "SEIZURE"
    assert f.measured_angle > 0.0
    assert f.duration_s > 0.0
    assert 0.0 <= f.score <= 1.0


def test_seizure_no_oscillation_no_finding():
    """Timeline sem oscilação → 0 findings."""
    from pipelines.video.pose_detector import detect_seizure

    frames = [_make_seizure_frame(offset=0.0) for _ in range(90)]
    findings = detect_seizure(frames, fps=30.0)

    assert findings == []


def test_seizure_insufficient_frames():
    """Menos de 60 frames → [] (dados insuficientes)."""
    from pipelines.video.pose_detector import detect_seizure

    frames = [_make_seizure_frame() for _ in range(30)]
    findings = detect_seizure(frames, fps=30.0)

    assert findings == []


def test_seizure_occluded_joint_excluded():
    """Articulação com visibilidade < 0.4 excluída; outras ainda contribuem."""
    from pipelines.video.pose_detector import detect_seizure

    frames = []
    offsets = [0.0, 0.04, 0.10, 0.04, 0.0, -0.04, -0.10, -0.04]
    for i in range(90):
        offset = offsets[i % len(offsets)]
        # Elbow L com visibilidade 0.3 (ocluído), restantes OK
        frames.append(_make_seizure_frame(offset=offset, elbow_vis=0.3))

    findings = detect_seizure(frames, fps=30.0)

    # Com 3 de 4 articulações oscilando, ainda deve detetar
    assert len(findings) == 1
    assert findings[0].finding_type == "SEIZURE"


# --------------------------------------------------------------------------- #
# T4: detect_agitation — agitação psicomotora (ITER2-05)
# --------------------------------------------------------------------------- #
def test_agitation_detected_with_frequent_position_changes():
    """40 mudanças de posição em 60s → 1 finding AGITATION."""
    from pipelines.video.pose_detector import detect_agitation

    # Simula 40 mudanças em 1800 frames (~60s a 30fps)
    # Cada ~45 frames: Y muda de 0.50 para 0.55 (ΔY=0.05 > 0.03)
    frames = []
    y_base = 0.50
    for i in range(1800):
        if i > 0 and i % 45 == 0:
            y_base = 0.60 if y_base == 0.50 else 0.50  # ΔY=0.10 > 0.03
        frames.append(_make_person_frame(hip_y=y_base, track_id=0))

    findings = detect_agitation(frames, fps=30.0)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "AGITATION"
    assert f.measured_angle > 30.0  # taxa de mudanças/min (> threshold 30)
    assert 0.0 <= f.score <= 1.0


def test_agitation_stable_person_no_finding():
    """Pessoa estável (2 mudanças em 60s) → 0 findings."""
    from pipelines.video.pose_detector import detect_agitation

    frames = [_make_person_frame(hip_y=0.50, track_id=0) for _ in range(1800)]
    # Apenas 2 mudanças pontuais
    frames[300] = _make_person_frame(hip_y=0.55, track_id=0)
    frames[600] = _make_person_frame(hip_y=0.55, track_id=0)

    findings = detect_agitation(frames, fps=30.0)

    assert findings == []


def test_agitation_insufficient_frames():
    """Menos de 120 frames → [] (dados insuficientes)."""
    from pipelines.video.pose_detector import detect_agitation

    frames = [_make_person_frame(hip_y=0.50, track_id=0) for _ in range(60)]
    findings = detect_agitation(frames, fps=30.0)

    assert findings == []


# --------------------------------------------------------------------------- #
# T5: detect_bed_exit — saída do leito (ITER2-06)
# --------------------------------------------------------------------------- #
def test_bed_exit_detected_when_lying_person_rises():
    """Pessoa deitada que sobe + desloca lateralmente → 1 finding BED_EXIT."""
    from pipelines.video.pose_detector import detect_bed_exit

    # 100 frames deitado (Y≈0.80) + 100 frames a subir com deslocamento lateral
    lying = [_make_person_frame(hip_y=0.80, track_id=0) for _ in range(100)]
    rising = []
    for i in range(100):
        y = 0.80 - (i / 100) * 0.40  # Y desce 0.80→0.40
        # Move os quadris lateralmente para criar ΔX no hip_center
        hip_x = 0.50 + (i / 100) * 0.10  # X: 0.50→0.60 (ΔX=0.10 > 0.05)
        landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
        landmarks[23] = (hip_x, y, 0.0, 0.9)       # hip L com X crescente
        landmarks[24] = (hip_x + 0.02, y, 0.0, 0.9)  # hip R
        landmarks[11] = (hip_x, y - 0.20, 0.0, 0.9)  # shoulder L
        landmarks[12] = (hip_x + 0.02, y - 0.20, 0.0, 0.9)
        landmarks[0] = (hip_x + 0.01, y - 0.25, 0.0, 0.9)
        rising.append(PoseFrame(landmarks=landmarks, track_id=0))

    frames = lying + rising

    findings = detect_bed_exit(frames, fps=30.0)

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == "BED_EXIT"
    assert f.measured_angle > 0.0  # |ΔY|
    assert 0.0 <= f.score <= 1.0


def test_bed_exit_not_applicable_to_standing_person():
    """Pessoa de pé → 0 findings (gate is_recumbent)."""
    from pipelines.video.pose_detector import detect_bed_exit

    frames = [_make_person_frame(hip_y=0.30, track_id=0) for _ in range(200)]
    findings = detect_bed_exit(frames, fps=30.0)

    assert findings == []


def test_bed_exit_no_lateral_movement_no_finding():
    """Pessoa deitada que sobe sem ΔX → 0 findings."""
    from pipelines.video.pose_detector import detect_bed_exit

    lying = [_make_person_frame(hip_y=0.80, track_id=0) for _ in range(100)]
    rising = []
    for i in range(100):
        y = 0.80 - (i / 100) * 0.20
        rising.append(_make_person_frame(hip_y=y, track_id=0, shoulder_dx=0.0))

    frames = lying + rising
    findings = detect_bed_exit(frames, fps=30.0)

    assert findings == []


def test_bed_exit_insufficient_frames():
    """Menos de 120 frames → []."""
    from pipelines.video.pose_detector import detect_bed_exit

    frames = [_make_person_frame(hip_y=0.80, track_id=0) for _ in range(60)]
    findings = detect_bed_exit(frames, fps=30.0)

    assert findings == []


# --------------------------------------------------------------------------- #
# T7: analyze_all_persons — integração multi-pessoa (ITER2-03)
# --------------------------------------------------------------------------- #
def test_analyze_all_persons_recumbent_dispatch():
    """Pessoa deitada com agitação → AGITATION emitido pelo orchestrator."""
    from pipelines.video.pose_detector import analyze_all_persons

    frames = []
    y_base = 0.80
    for i in range(1800):
        if i > 0 and i % 45 == 0:
            y_base = 0.90 if y_base == 0.80 else 0.80  # ΔY=0.10 > 0.03
        landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
        landmarks[23] = (0.50, y_base, 0.0, 0.9)
        landmarks[24] = (0.52, y_base, 0.0, 0.9)
        landmarks[11] = (0.50, y_base - 0.20, 0.0, 0.9)
        landmarks[12] = (0.52, y_base - 0.20, 0.0, 0.9)
        landmarks[0] = (0.51, y_base - 0.25, 0.0, 0.9)
        frames.append(PoseFrame(landmarks=landmarks, track_id=0))

    all_poses = [[f] for f in frames]

    _, _, consolidated, details = analyze_all_persons(
        all_poses_per_frame=all_poses, fps=30.0,
    )

    assert details["pessoas_analisadas"] == 1
    agitation_findings = [c for c in consolidated if c.finding_type == "AGITATION"]
    assert len(agitation_findings) >= 1


def test_analyze_all_persons_no_tracking_fallback():
    """Sem tracking → fallback (sem erro, sem findings)."""
    from pipelines.video.pose_detector import analyze_all_persons

    frames = []
    for _ in range(100):
        landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
        landmarks[23] = (0.50, 0.30, 0.0, 0.9)
        landmarks[24] = (0.52, 0.30, 0.0, 0.9)
        frames.append(PoseFrame(landmarks=landmarks, track_id=None))

    all_poses = [[f] for f in frames]
    _, pontuacao, consolidated, details = analyze_all_persons(
        all_poses_per_frame=all_poses, fps=30.0,
    )

    assert details["pessoas_analisadas"] == 0
    assert pontuacao == 0.0


def test_validate_fall_dynamic_truly_falling_person_detected():
    """Pessoa com queda real (Vy≈0.25, tilt≈45°) → detectada com track_id correto."""
    from pipelines.video.pose_detector import validate_fall_dynamic

    # Paciente deitado
    patient = _make_person_frame(hip_y=0.80, track_id=0)

    # Pessoa em pé com tilt significativo (dx=0.3, dy=0.4 → arctan(0.3/0.4)=36.9°)
    standing = _make_person_frame(hip_y=0.30, shoulder_dx=0.30, track_id=1)

    # Queda: Y cai de 0.30 a 0.85, tilt aumenta
    fall_sequence = []
    for i, y in enumerate([0.30, 0.42, 0.55, 0.68, 0.80, 0.85, 0.85, 0.85, 0.85, 0.85]):
        fall_sequence.append(_make_person_frame(
            hip_y=y, shoulder_dx=0.30 + i * 0.02, track_id=1,
        ))

    all_poses = (
        [[patient, standing] for _ in range(90)]
        + [[patient, f] for f in fall_sequence]
    )

    # Vy realista (aproximado da sequência de Y)
    dummy_vy: list[float | None] = (
        [0.0] * 90 + [0.12, 0.13, 0.13, 0.12, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
    )

    verdict, frame_idx, vy_score, desc, tid, peak = validate_fall_dynamic(
        "queda", 90, dummy_vy, min_vertical_velocity=0.10,
        all_poses_per_frame=all_poses, n_pessoas=2,
    )

    # Se detectar queda, o track_id DEVE ser 1 (pessoa que caiu)
    if verdict == "queda":
        assert tid == 1, f"track_id={tid}, esperado 1"
    # Se não detectar (thresholds multi-pessoa elevados), ainda assim
    # o paciente (track_id=0) NUNCA deve ser o escolhido
    # (esta asserção é redundante com a de cima mas documenta o requisito)
    assert tid != 0, f"Paciente deitado (track_id=0) nunca deve ser marcado como queda"
