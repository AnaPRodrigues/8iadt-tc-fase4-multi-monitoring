"""Extração de keypoints de pose via MediaPipe.

A versão instalada (`mediapipe==0.10.35`) não tem mais a API antiga
(`mp.solutions.pose`) -- só a Task API nova (`mediapipe.tasks.python.vision`),
que exige baixar um modelo `.task` separado (não vem embutido no pip package).
Confirmado empiricamente no Design; não é uma escolha arbitrária.
"""

import urllib.request
from pathlib import Path
from typing import Any

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


def create_landmarker(model_path: Path, num_poses: int = 3) -> vision.PoseLandmarker:
    """Cria o `PoseLandmarker` (Task API) a partir do modelo já em cache.

    ``num_poses`` controla quantos esqueletos o MediaPipe tenta detetar por frame
    (default 3 — cobre paciente + 2 profissionais no quarto).
    """
    base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=num_poses,
    )
    return vision.PoseLandmarker.create_from_options(options)


def extract_all_keypoints(
    frame_path: Path, landmarker: vision.PoseLandmarker
) -> list[PoseFrame]:
    """Roda o `PoseLandmarker` e devolve **todos** os esqueletos detetados.

    Usa YOLOv8n para detetar a região da pessoa e recortar o frame antes do
    MediaPipe — reduz alucinações em objetos de fundo (sofás, impressoras).
    Se o YOLO não encontrar pessoas ou não estiver disponível, usa o frame
    inteiro como fallback.

    Devolve lista vazia se nenhuma pessoa for detetada.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")

    # Tenta YOLO crop primeiro; fallback para frame inteiro
    crop_result = _person_crop(frame_path)
    if crop_result is not None:
        cropped, (cx, cy, cw, ch) = crop_result
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

        if result.pose_landmarks:
            # Mapeia coordenadas de volta para o frame original
            poses: list[PoseFrame] = []
            for pose_landmarks in result.pose_landmarks:
                landmarks = []
                for lm in pose_landmarks:
                    # Converte coordenadas normalizadas do crop para o frame original
                    orig_x = (lm.x * cw + cx) / frame.shape[1]
                    orig_y = (lm.y * ch + cy) / frame.shape[0]
                    landmarks.append((orig_x, orig_y, lm.z, lm.visibility))
                poses.append(PoseFrame(landmarks=landmarks))
            return poses

    # Fallback: frame inteiro
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if not result.pose_landmarks:
        return []

    return [
        PoseFrame(landmarks=[(lm.x, lm.y, lm.z, lm.visibility) for lm in pose_landmarks])
        for pose_landmarks in result.pose_landmarks
    ]


_PERSON_DETECTOR: Any = None  # lazy-loaded YOLOv8n


def _get_person_detector() -> Any:
    """YOLOv8n pré-treinado em COCO para detetar pessoas no frame.

    Carregado sob demanda (lazy) — o modelo só é baixado na primeira
    utilização. Devolve ``None`` se o modelo não estiver disponível.
    """
    global _PERSON_DETECTOR
    if _PERSON_DETECTOR is None:
        try:
            from ultralytics import YOLO
            _PERSON_DETECTOR = YOLO("yolov8n.pt")
            log.info("detector de pessoas YOLOv8n carregado")
        except Exception as exc:
            log.warning("não foi possível carregar YOLOv8n: %s", exc)
            _PERSON_DETECTOR = False  # sentinel: tentámos e falhou
    return _PERSON_DETECTOR if _PERSON_DETECTOR is not False else None


def _person_crop(frame_path: Path) -> tuple[Any, tuple[int, int, int, int]] | None:
    """Deteta a maior pessoa no frame e devolve a região recortada.

    Usa YOLOv8n (COCO classe 0 = person). Devolve ``(imagem_recortada, (x, y, w, h))``
    ou ``None`` se nenhuma pessoa for encontrada ou o modelo não estiver disponível.
    """
    detector = _get_person_detector()
    if detector is None:
        return None

    image = cv2.imread(str(frame_path))
    if image is None:
        return None

    results = detector.predict(image, conf=0.3, classes=[0], verbose=False, save=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None

    # Maior bounding box de pessoa (filtra deteções pequenas/ruído)
    best = max(boxes, key=lambda b: (b.xyxy[0][2] - b.xyxy[0][0]) * (b.xyxy[0][3] - b.xyxy[0][1]))
    x1, y1, x2, y2 = [int(v) for v in best.xyxy[0]]
    h, w = image.shape[:2]
    # Adiciona 20% de padding, sem sair do frame
    pad_x = int((x2 - x1) * 0.2)
    pad_y = int((y2 - y1) * 0.2)
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)

    cropped = image[y1:y2, x1:x2]
    return (cropped, (x1, y1, x2 - x1, y2 - y1))


def extract_keypoints(frame_path: Path, landmarker: vision.PoseLandmarker) -> PoseFrame | None:
    """Wrapper retrocompatível: devolve o primeiro esqueleto ou ``None``.

    Delegar a ``extract_all_keypoints`` mantém a semântica original (1 pessoa =
    primeiro elemento; 0 pessoas = ``None``) sem duplicar a lógica de inferência.
    """
    all_poses = extract_all_keypoints(frame_path, landmarker)
    return all_poses[0] if all_poses else None
