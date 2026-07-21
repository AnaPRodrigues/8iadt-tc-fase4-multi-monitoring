"""Testes de `pose_detector.py` -- derivados de VIDEO-03, VIDEO-05 e VIDEO-14."""

import json
from pathlib import Path

import pytest

from pipelines.video.models import MovementWindow
from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_keypoints
from pipelines.video.pose_detector import classify_sequence, save_fall_evidence

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
