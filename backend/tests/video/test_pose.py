"""Testes de `pose.py` -- extração de keypoints e caso de frame sem pessoa.

Download real do modelo `.task` (sem mock, por instrução explícita):
compartilhado entre os testes do módulo via fixture `scope="module"` para não
baixar 5.7MB repetidas vezes.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from pipelines.video import pose as pose_module
from pipelines.video.pose import (
    create_landmarker,
    ensure_pose_model,
    extract_all_keypoints,
    extract_keypoints,
)

_URFD_FRAME = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "urfd"
    / "fall-01"
    / "fall-01-cam0-rgb"
    / "fall-01-cam0-rgb-050.png"
)


@pytest.fixture(scope="module")
def model_path(tmp_path_factory):
    cache_dir = tmp_path_factory.mktemp("pose_model_cache")
    return ensure_pose_model(cache_dir)


@pytest.fixture(scope="module")
def landmarker(model_path):
    return create_landmarker(model_path)


def test_ensure_pose_model_baixa_arquivo_valido(tmp_path):
    path = ensure_pose_model(tmp_path)

    assert path.is_file()
    assert path.name == "pose_landmarker_full.task"
    assert path.stat().st_size > 0


def test_ensure_pose_model_idempotente_nao_rebaixa(tmp_path, monkeypatch):
    path1 = ensure_pose_model(tmp_path)
    mtime_original = path1.stat().st_mtime

    def _falha_se_chamado(*_args, **_kwargs):
        raise AssertionError("urlretrieve não deveria ser chamado com o modelo já em cache")

    monkeypatch.setattr(pose_module.urllib.request, "urlretrieve", _falha_se_chamado)

    path2 = ensure_pose_model(tmp_path)

    assert path2 == path1
    assert path2.stat().st_mtime == mtime_original


def test_extract_keypoints_frame_real_devolve_33_landmarks(landmarker):
    pose_frame = extract_keypoints(_URFD_FRAME, landmarker)

    assert pose_frame is not None
    assert len(pose_frame.landmarks) == 33
    for x, y, z, visibility in pose_frame.landmarks:
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert isinstance(z, float)
        assert isinstance(visibility, float)


def test_extract_keypoints_frame_sem_pessoa_devolve_none(tmp_path, landmarker):
    frame_vazio = tmp_path / "vazio.png"
    cv2.imwrite(str(frame_vazio), np.zeros((480, 640, 3), dtype="uint8"))

    pose_frame = extract_keypoints(frame_vazio, landmarker)

    assert pose_frame is None


def test_extract_keypoints_frame_inexistente_levanta_file_not_found_error(landmarker):
    with pytest.raises(FileNotFoundError):
        extract_keypoints(Path("/tmp/frame-que-nao-existe-de-verdade.png"), landmarker)


# --------------------------------------------------------------------------- #
# extract_all_keypoints — multi-person
# --------------------------------------------------------------------------- #
def test_extract_all_keypoints_frame_real_devolve_lista_nao_vazia(landmarker):
    poses = extract_all_keypoints(_URFD_FRAME, landmarker)

    assert isinstance(poses, list)
    assert len(poses) >= 1
    for pf in poses:
        assert len(pf.landmarks) == 33


def test_extract_all_keypoints_frame_sem_pessoa_devolve_lista_vazia(tmp_path, landmarker):
    frame_vazio = tmp_path / "vazio.png"
    cv2.imwrite(str(frame_vazio), np.zeros((480, 640, 3), dtype="uint8"))

    poses = extract_all_keypoints(frame_vazio, landmarker)

    assert isinstance(poses, list)
    assert len(poses) == 0


def test_extract_keypoints_backward_compat_frame_real(landmarker):
    """extract_keypoints deve devolver o primeiro esqueleto (mesmo de antes)."""
    pf = extract_keypoints(_URFD_FRAME, landmarker)
    all_poses = extract_all_keypoints(_URFD_FRAME, landmarker)

    assert pf is not None
    assert len(all_poses) >= 1
    # Os landmarks do primeiro esqueleto devem ser idênticos
    assert pf.landmarks == all_poses[0].landmarks


def test_extract_keypoints_backward_compat_frame_sem_pessoa(tmp_path, landmarker):
    frame_vazio = tmp_path / "vazio2.png"
    cv2.imwrite(str(frame_vazio), np.zeros((480, 640, 3), dtype="uint8"))

    pf = extract_keypoints(frame_vazio, landmarker)

    assert pf is None


def test_create_landmarker_respeita_num_poses(tmp_path):
    model_path = ensure_pose_model(tmp_path)

    # num_poses=1 deve criar landmarker sem erro
    lm1 = create_landmarker(model_path, num_poses=1)
    assert lm1 is not None

    # num_poses=5 deve criar landmarker sem erro
    lm5 = create_landmarker(model_path, num_poses=5)
    assert lm5 is not None
