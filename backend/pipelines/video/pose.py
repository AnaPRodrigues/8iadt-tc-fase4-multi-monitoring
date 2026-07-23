"""Extração de keypoints de pose via MediaPipe.

A versão instalada (`mediapipe==0.10.35`) não tem mais a API antiga
(`mp.solutions.pose`) -- só a Task API nova (`mediapipe.tasks.python.vision`),
que exige baixar um modelo `.task` separado (não vem embutido no pip package).
Confirmado empiricamente no Design; não é uma escolha arbitrária.
"""

import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from common.logging import get_logger
from pipelines.video.models import PoseFrame

log = get_logger("video.pose")

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
_MODEL_FILENAME = "pose_landmarker_lite.task"


def ensure_pose_model(cache_dir: Path) -> Path:
    """Baixa o modelo `.task` sob demanda; idempotente (checa antes de baixar).

    Mesmo princípio de cache de `yolov8n.pt` do ultralytics: uma segunda chamada
    com o arquivo já presente não dispara nova requisição de rede.
    """
    cache_dir = Path(cache_dir)
    model_path = cache_dir / _MODEL_FILENAME
    if model_path.is_file():
        log.info("modelo de pose já em cache: %s", model_path)
        return model_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info("baixando modelo de pose de %s", _MODEL_URL)
    try:
        urllib.request.urlretrieve(_MODEL_URL, model_path)
    except Exception as exc:
        raise RuntimeError(f"falha ao baixar o modelo de pose de {_MODEL_URL}: {exc}") from exc

    return model_path


def create_landmarker(model_path: Path) -> vision.PoseLandmarker:
    """Cria o `PoseLandmarker` (Task API) a partir do modelo já em cache."""
    base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
    )
    return vision.PoseLandmarker.create_from_options(options)


def extract_keypoints(frame_path: Path, landmarker: vision.PoseLandmarker) -> PoseFrame | None:
    """Roda o `PoseLandmarker` num frame real; `None` se nenhuma pessoa detectada.

    Nunca lança exceção nem inventa landmarks para um frame sem pessoa
    detectável -- o chamador decide o que fazer com a ausência.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if not result.pose_landmarks:
        return None

    landmarks = [(lm.x, lm.y, lm.z, lm.visibility) for lm in result.pose_landmarks[0]]
    return PoseFrame(landmarks=landmarks)
