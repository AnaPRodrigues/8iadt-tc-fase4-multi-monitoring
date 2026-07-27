"""Testes de ``pose_evidence.draw_annotated_frame`` — esqueleto + articulações
destacadas + ângulos sobrepostos."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from pipelines.video.models import PoseFrame, PosturalFinding
from pipelines.video.pose_evidence import draw_annotated_frame


def _make_frame() -> PoseFrame:
    """PoseFrame sintético com todos os landmarks visíveis."""
    landmarks = [(0.5, 0.5, 0.0, 0.9) for _ in range(33)]
    # Configura alguns landmarks em posições distintas para o esqueleto ser visível
    landmarks[11] = (0.45, 0.30, 0.0, 0.9)  # shoulder L
    landmarks[12] = (0.55, 0.30, 0.0, 0.9)  # shoulder R
    landmarks[23] = (0.45, 0.55, 0.0, 0.9)  # hip L
    landmarks[24] = (0.55, 0.55, 0.0, 0.9)  # hip R
    landmarks[25] = (0.45, 0.70, 0.0, 0.9)  # knee L
    landmarks[26] = (0.55, 0.70, 0.0, 0.9)  # knee R
    landmarks[27] = (0.40, 0.85, 0.0, 0.9)  # ankle L
    landmarks[28] = (0.60, 0.85, 0.0, 0.9)  # ankle R
    landmarks[13] = (0.35, 0.40, 0.0, 0.9)  # elbow L
    landmarks[14] = (0.65, 0.40, 0.0, 0.9)  # elbow R
    landmarks[15] = (0.30, 0.50, 0.0, 0.9)  # wrist L
    landmarks[16] = (0.70, 0.50, 0.0, 0.9)  # wrist R
    return PoseFrame(landmarks=landmarks)


def _blank_image(tmp_path: Path, name: str = "frame.png") -> Path:
    """Imagem sintética 640x480 para desenho."""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 240
    path = tmp_path / name
    cv2.imwrite(str(path), img)
    return path


def _knee_finding(angle: float = 62.0) -> PosturalFinding:
    return PosturalFinding(
        finding_type="POSTURAL_DEVIATION",
        joint_name="knee_left",
        measured_angle=angle,
        expected_angle=70.0,
        duration_s=1.5,
        frame_index=95,
        score=0.42,
        description=f"Amplitude articular reduzida (alcançado: {angle:.0f}°, esperado: >70°).",
    )


def _trunk_finding(angle: float = 34.0) -> PosturalFinding:
    return PosturalFinding(
        finding_type="TRUNK_TILT",
        joint_name=None,
        measured_angle=angle,
        expected_angle=30.0,
        duration_s=4.2,
        frame_index=120,
        score=0.57,
        description=f"Inclinação de tronco sustentada ({angle:.0f}° por 4.2s).",
    )


def _fall_finding() -> PosturalFinding:
    return PosturalFinding(
        finding_type="FALL_DETECTED",
        joint_name=None,
        measured_angle=0.0,
        expected_angle=0.0,
        duration_s=0.0,
        frame_index=50,
        score=0.78,
        description="Queda detectada.",
    )


# --------------------------------------------------------------------------- #
# draw_annotated_frame
# --------------------------------------------------------------------------- #
def test_draw_with_postural_deviation_produces_valid_png(tmp_path):
    """POSTURAL_DEVIATION → PNG com marcadores amarelos."""
    frame = _make_frame()
    img = _blank_image(tmp_path)
    out = tmp_path / "output.png"

    result = draw_annotated_frame(img, frame, [_knee_finding(62.0)], out)

    assert result == out
    assert out.is_file()
    # Verifica que é uma imagem PNG válida
    loaded = cv2.imread(str(out))
    assert loaded is not None
    assert loaded.shape == (480, 640, 3)


def test_draw_with_trunk_tilt_produces_valid_png(tmp_path):
    """TRUNK_TILT → PNG com linha da espinha vermelha."""
    frame = _make_frame()
    img = _blank_image(tmp_path)
    out = tmp_path / "output.png"

    result = draw_annotated_frame(img, frame, [_trunk_finding(34.0)], out)

    assert result == out
    assert out.is_file()
    loaded = cv2.imread(str(out))
    assert loaded is not None


def test_draw_with_multiple_findings(tmp_path):
    """Múltiplos findings no mesmo frame → PNG com todos os destaques."""
    frame = _make_frame()
    img = _blank_image(tmp_path)
    out = tmp_path / "output.png"

    result = draw_annotated_frame(
        img, frame, [_knee_finding(62.0), _trunk_finding(34.0)], out,
    )

    assert result == out
    assert out.is_file()
    loaded = cv2.imread(str(out))
    assert loaded is not None


def test_draw_frame_inexistente_levanta_file_not_found_error(tmp_path):
    """Frame inexistente → FileNotFoundError."""
    frame = _make_frame()
    out = tmp_path / "output.png"

    with pytest.raises(FileNotFoundError):
        draw_annotated_frame(tmp_path / "nao-existe.png", frame, [], out)
