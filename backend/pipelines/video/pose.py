"""Extração de keypoints de pose via MediaPipe com pré-detecção YOLO.

A versão instalada (`mediapipe==0.10.35`) não tem mais a API antiga
(`mp.solutions.pose`) -- só a Task API nova (`mediapipe.tasks.python.vision`),
que exige baixar um modelo `.task` separado (não vem embutido no pip package).
Confirmado empiricamente no Design; não é uma escolha arbitrária.

O YOLOv8n (COCO, ~6MB) deteta regiões de pessoas no frame antes do MediaPipe.
Cada região é recortada individualmente, eliminando alucinações em objetos de
fundo (mesas, computadores) e aumentando a resolução efetiva para pessoas
distantes em câmeras de teto.
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

# --------------------------------------------------------------------------- #
# YOLO person detector (lazy-loaded)
# --------------------------------------------------------------------------- #
_yolo_detector: "YOLO | None | Literal[False]" = None  # type: ignore[name-defined]


def _get_yolo():
    """YOLOv8n pré-treinado em COCO, carregado sob demanda."""
    global _yolo_detector
    if _yolo_detector is None:
        try:
            from ultralytics import YOLO
            _yolo_detector = YOLO("yolov8n.pt")
            log.info("detector de pessoas YOLOv8n carregado")
        except Exception as exc:
            log.warning("não foi possível carregar YOLOv8n: %s", exc)
            _yolo_detector = False
    return _yolo_detector if _yolo_detector is not False else None


def _all_person_boxes(image: "cv2.Mat") -> list[tuple[int, int, int, int]]:  # type: ignore[valid-type]
    """Todas as bounding boxes de pessoas (COCO classe 0) no frame.

    Devolve lista de ``(x1, y1, x2, y2)`` em coordenadas absolutas do frame.
    Lista vazia se o YOLO não estiver disponível ou não encontrar pessoas.
    """
    yolo = _get_yolo()
    if yolo is None:
        return []
    results = yolo.predict(image, conf=0.25, classes=[0], verbose=False, save=False)
    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return []
    return [(int(b.xyxy[0][0]), int(b.xyxy[0][1]), int(b.xyxy[0][2]), int(b.xyxy[0][3]))
            for b in boxes]

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
    """YOLO multi-crop → MediaPipe por pessoa → coordenadas normalizadas.

    Para cada pessoa detetada pelo YOLO (COCO classe 0, conf ≥ 0.25):
    1. Recorta a região com 20% de padding
    2. Executa o MediaPipe apenas nessa região
    3. Mapeia as coordenadas de volta para o frame completo

    Com YOLO, o MediaPipe não vê objetos de fundo (mesas, computadores)
    e ganha resolução efetiva para pessoas distantes. Se o YOLO não
    encontrar ninguém, faz fallback para o frame inteiro.

    Devolve lista vazia se nenhuma pessoa for detetada.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")
    h, w = frame.shape[:2]

    boxes = _all_person_boxes(frame)
    all_poses: list[PoseFrame] = []

    for x1, y1, x2, y2 in boxes:
        # Padding de 20% sem sair do frame
        pad_x = int((x2 - x1) * 0.2)
        pad_y = int((y2 - y1) * 0.2)
        cx1, cy1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
        cx2, cy2 = min(w, x2 + pad_x), min(h, y2 + pad_y)
        cw, ch = cx2 - cx1, cy2 - cy1
        if cw <= 0 or ch <= 0:
            continue

        cropped = frame[cy1:cy2, cx1:cx2]
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

        if result.pose_landmarks:
            for pose_landmarks in result.pose_landmarks:
                landmarks = [
                    ((lm.x * cw + cx1) / w, (lm.y * ch + cy1) / h, lm.z, lm.visibility)
                    for lm in pose_landmarks
                ]
                all_poses.append(PoseFrame(landmarks=landmarks))

    if all_poses:
        return all_poses

    # Fallback: YOLO não encontrou pessoas → frame inteiro
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if not result.pose_landmarks:
        return []

    return [
        PoseFrame(landmarks=[(lm.x, lm.y, lm.z, lm.visibility) for lm in pose_landmarks])
        for pose_landmarks in result.pose_landmarks
    ]


def extract_keypoints(frame_path: Path, landmarker: vision.PoseLandmarker) -> PoseFrame | None:
    """Wrapper retrocompatível: devolve o primeiro esqueleto ou ``None``.

    Delegar a ``extract_all_keypoints`` mantém a semântica original (1 pessoa =
    primeiro elemento; 0 pessoas = ``None``) sem duplicar a lógica de inferência.
    """
    all_poses = extract_all_keypoints(frame_path, landmarker)
    return all_poses[0] if all_poses else None
