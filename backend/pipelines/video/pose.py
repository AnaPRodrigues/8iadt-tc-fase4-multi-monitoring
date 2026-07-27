"""Extração de keypoints de pose via MediaPipe com pré-detecção YOLO.

A versão instalada (`mediapipe==0.10.35`) não tem mais a API antiga
(`mp.solutions.pose`) -- só a Task API nova (`mediapipe.tasks.python.vision`),
que exige baixar um modelo `.task` separado (não vem embutido no pip package).
Confirmado empiricamente no Design; não é uma escolha arbitrária.

Detector de pessoas configurável:
- ``yolov8n`` (default): YOLOv8nano via ultralytics (~6 MB, COCO).
- ``yolo_nas_s`` / ``yolo_nas_m``: YOLO-NAS via SuperGradients (ONNX ou
  checkpoint), carregado sob demanda. Fallback silencioso para YOLOv8n se o
  SuperGradients não estiver instalado.

Tracking de identidade persistente:
- Um rastreador IoU (Intersection-over-Union) associa bounding boxes entre
  frames consecutivos, atribuindo um ``track_id`` estável a cada pessoa.
- O ``track_id`` é propagado para ``PoseFrame``, permitindo que a evidência
  de queda referencie inequivocamente a pessoa correta (em vez de depender
  do índice posicional da lista).
"""

import os
import urllib.request
from pathlib import Path
from typing import Literal

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from common.logging import get_logger
from pipelines.video.models import PoseFrame

log = get_logger("video.pose")

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)
_MODEL_FILENAME = "pose_landmarker_full.task"

# --------------------------------------------------------------------------- #
# Backend do detector de pessoas (configurável)
# --------------------------------------------------------------------------- #
_DetectorBackend = Literal["yolov8n", "yolo_nas_s", "yolo_nas_m"]
_DETECTOR_BACKEND: _DetectorBackend = os.environ.get(
    "POSE_DETECTOR_BACKEND", "yolo_nas_s"
)  # type: ignore[arg-type]


def set_detector_backend(backend: str) -> None:
    """Altera o backend do detector de pessoas (válido até à próxima chamada).

    Valores aceites: ``"yolov8n"``, ``"yolo_nas_s"``, ``"yolo_nas_m"``.
    """
    global _DETECTOR_BACKEND
    valid = {"yolov8n", "yolo_nas_s", "yolo_nas_m"}
    if backend not in valid:
        raise ValueError(f"backend inválido: {backend!r} (use {sorted(valid)})")
    _DETECTOR_BACKEND = backend  # type: ignore[assignment]
    log.info("detector backend alterado para %s", backend)


# --------------------------------------------------------------------------- #
# YOLOv8n (ultralytics) — lazy-loaded
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


# --------------------------------------------------------------------------- #
# YOLO-NAS — SuperGradients (preferencial) ou ONNX (fallback leve)
# --------------------------------------------------------------------------- #
_yolo_nas_detector: "object | None | Literal[False]" = None
_yolo_nas_variant: str | None = None  # qual variante está em cache
_yolo_nas_onnx_session: "object | None | Literal[False]" = None
_yolo_nas_onnx_variant: str | None = None

_ONNX_INPUT_SIZE = (640, 640)  # resolução de entrada do YOLO-NAS


def _ensure_onnx_model(variant: str, cache_dir: Path) -> Path | None:
    """Localiza (ou descarrega) o modelo ONNX do YOLO-NAS.

    Ordem de procura:
    1. ``<cache_dir>/<variant>.onnx`` — ficheiro local (já exportado).
    2. Download automático de URL oficial do Deci AI (se disponível).

    Para exportar manualmente o modelo ONNX a partir do SuperGradients::

        from super_gradients.training import models
        model = models.get("yolo_nas_s", pretrained_weights="coco")
        model.export("yolo_nas_s.onnx", input_shape=(1, 3, 640, 640),
                      nms=True, confidence_threshold=0.25)

    O ficheiro ``.onnx`` resultante deve ser colocado em ``<cache_dir>/``.
    """
    onnx_path = cache_dir / f"{variant}.onnx"
    if onnx_path.is_file():
        log.info("modelo ONNX %s encontrado em cache: %s", variant, onnx_path)
        return onnx_path

    # Tenta download automático (URL oficial — Axelera AI / Deci model zoo)
    url = (
        "https://media.axelera.ai/artifacts/model_cards/weights/"
        "yolo/object_detection/yolo_nas_s.onnx"
        if variant == "yolo_nas_s"
        else "https://media.axelera.ai/artifacts/model_cards/weights/"
        "yolo/object_detection/yolo_nas_m.onnx"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info("modelo ONNX não encontrado localmente; tentando download de %s", url)

    import urllib.request as _request

    try:
        _request.urlretrieve(url, onnx_path)
        log.info("modelo ONNX %s cached em %s", variant, onnx_path)
        return onnx_path
    except Exception as exc:
        # Limpa ficheiro parcial em caso de falha
        if onnx_path.exists():
            onnx_path.unlink()
        log.warning(
            "download automático falhou (%s). Exporte o modelo manualmente "
            "com SuperGradients e coloque-o em %s",
            exc, onnx_path,
        )
        return None


def _get_yolo_nas_onnx(variant: str = "yolo_nas_s", cache_dir: Path | None = None):
    """YOLO-NAS via ONNX Runtime (alternativa leve ao SuperGradients).

    Carrega um modelo ONNX pré-exportado com pós-processamento (NMS incluído).
    O modelo é descarregado automaticamente na primeira utilização e cached em
    ``cache_dir`` (default: ``models/`` relativo ao CWD).
    """
    global _yolo_nas_onnx_session, _yolo_nas_onnx_variant

    if _yolo_nas_onnx_session is not None and _yolo_nas_onnx_variant == variant:
        return _yolo_nas_onnx_session if _yolo_nas_onnx_session is not False else None

    if _yolo_nas_onnx_variant is not None and _yolo_nas_onnx_variant != variant:
        _yolo_nas_onnx_session = None
        _yolo_nas_onnx_variant = None

    if cache_dir is None:
        cache_dir = Path("models")

    onnx_path = _ensure_onnx_model(variant, cache_dir)
    if onnx_path is None:
        _yolo_nas_onnx_session = False
        _yolo_nas_onnx_variant = variant
        return None

    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        _yolo_nas_onnx_session = session
        _yolo_nas_onnx_variant = variant
        log.info("detector de pessoas %s (ONNX) carregado de %s", variant, onnx_path)
        return session
    except ImportError:
        log.warning("onnxruntime não instalado — faça 'pip install onnxruntime'")
        _yolo_nas_onnx_session = False
        _yolo_nas_onnx_variant = variant
        return None
    except Exception as exc:
        log.warning("falha ao carregar ONNX %s: %s", variant, exc)
        _yolo_nas_onnx_session = False
        _yolo_nas_onnx_variant = variant
        return None


def _get_yolo_nas(variant: str = "yolo_nas_s"):
    """YOLO-NAS: tenta SuperGradients primeiro, depois ONNX.

    Suporta ``yolo_nas_s`` (~13M params) e ``yolo_nas_m`` (~30M params).
    - SuperGradients: API completa, requer instalação do pacote.
    - ONNX Runtime: alternativa leve (~150 MB), modelo descarregado sob demanda.

    Se nenhum dos dois estiver disponível, devolve ``None`` e
    ``_get_detector()`` faz fallback para YOLOv8n.
    """
    global _yolo_nas_detector, _yolo_nas_variant

    if _yolo_nas_detector is not None and _yolo_nas_variant == variant:
        return _yolo_nas_detector if _yolo_nas_detector is not False else None

    if _yolo_nas_variant is not None and _yolo_nas_variant != variant:
        _yolo_nas_detector = None
        _yolo_nas_variant = None

    # 1) Tenta SuperGradients
    try:
        from super_gradients.training import models

        model = models.get(variant, pretrained_weights="coco")
        _yolo_nas_detector = model
        _yolo_nas_variant = variant
        log.info("detector de pessoas %s (YOLO-NAS/SuperGradients) carregado", variant)
        return _yolo_nas_detector
    except ImportError:
        log.debug("super_gradients não disponível, tentando ONNX para %s", variant)
    except Exception as exc:
        log.debug("super_gradients falhou para %s: %s; tentando ONNX", variant, exc)

    # 2) Fallback: ONNX Runtime
    onnx_session = _get_yolo_nas_onnx(variant)
    if onnx_session is not None:
        _yolo_nas_detector = onnx_session
        _yolo_nas_variant = variant
        return onnx_session

    log.warning(
        "%s indisponível (nem SuperGradients nem ONNX encontrados); "
        "fallback para YOLOv8n",
        variant,
    )
    _yolo_nas_detector = False
    _yolo_nas_variant = variant
    return None  # deixa _get_detector() gerir o fallback


def _get_detector():
    """Devolve o detector ativo conforme o backend configurado."""
    if _DETECTOR_BACKEND in ("yolo_nas_s", "yolo_nas_m"):
        nas = _get_yolo_nas(_DETECTOR_BACKEND)
        if nas is not None:
            # Determina se é sessão ONNX ou modelo SuperGradients
            try:
                import onnxruntime as ort
                if isinstance(nas, ort.InferenceSession):
                    return ("nas_onnx", nas)
            except ImportError:
                pass
            return ("nas", nas)
        # Fallback implícito: se YOLO-NAS falhou, tenta YOLOv8n
        log.info("fallback para YOLOv8n (YOLO-NAS indisponível)")
    return ("yolo", _get_yolo())


# --------------------------------------------------------------------------- #
# IoU tracker — associação de identidade entre frames consecutivos
# --------------------------------------------------------------------------- #
def _box_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
    """Intersection-over-Union entre duas bounding boxes (x1, y1, x2, y2)."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(0, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(0, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


# Estado do rastreador (limpo entre sequências via reset_person_tracker)
_tracker_state: dict = {
    "next_id": 0,
    "previous_boxes": [],   # list[tuple[int,int,int,int]]
    "previous_ids": [],     # list[int]
    "lost_tracks": {},      # track_id -> (box, frames_since_seen)
}
_IOU_THRESHOLD = 0.3       # IoU mínimo para considerar a mesma pessoa
_MAX_LOST_FRAMES = 10       # frames antes de descartar um track perdido

# Filtros anti-falso-positivo (POSE-22)
_DETECTION_CONFIDENCE = 0.45  # confiança mínima do detector (0.25 → 0.45)
_MIN_BOX_WIDTH = 30           # largura mínima da bbox (px) — ignora ruídos
_MIN_BOX_HEIGHT = 50          # altura mínima da bbox (px) — pessoa real vs. objeto
_MIN_BOX_AREA_RATIO = 0.015   # área mínima da bbox relativa ao frame (1.5%)
_MIN_BOX_PIXEL_AREA = 1500    # área mínima absoluta (px²)


def reset_person_tracker() -> None:
    """Reinicia o estado do rastreador de pessoas (entre sequências distintas)."""
    global _tracker_state
    _tracker_state = {
        "next_id": 0,
        "previous_boxes": [],
        "previous_ids": [],
        "lost_tracks": {},
    }
    # Reinicia também o estado de persistência do ground person (ITER2-01)
    from pipelines.video.pose_features import reset_ground_person_state
    reset_ground_person_state()


def _assign_track_ids(
    boxes: list[tuple[int, int, int, int]],
) -> list[int]:
    """Associa identidades estáveis às bounding boxes via IoU guloso.

    O algoritmo:
    1. Calcula a matriz de IoU entre todas as boxes atuais e as do frame anterior.
    2. Faz matching guloso (maior IoU primeiro), exigindo IoU ≥ threshold.
    3. Boxes não emparelhadas recebem um novo ``track_id``.
    4. Tracks perdidos são mantidos em cache por até ``_MAX_LOST_FRAMES``
       para recuperação após oclusão breve.

    Devolve uma lista de ``track_id`` alinhada com ``boxes``.
    """
    global _tracker_state

    if not boxes:
        # Nenhuma deteção: envelhece tracks perdidos
        expired = [
            tid for tid, (_, age) in _tracker_state["lost_tracks"].items()
            if age >= _MAX_LOST_FRAMES
        ]
        for tid in expired:
            del _tracker_state["lost_tracks"][tid]
        for tid in list(_tracker_state["lost_tracks"]):
            box, age = _tracker_state["lost_tracks"][tid]
            _tracker_state["lost_tracks"][tid] = (box, age + 1)
        _tracker_state["previous_boxes"] = []
        _tracker_state["previous_ids"] = []
        return []

    prev_boxes = list(_tracker_state["previous_boxes"])
    prev_ids = list(_tracker_state["previous_ids"])

    # Adiciona tracks perdidos recentes ao pool de matching
    for tid, (box, age) in _tracker_state["lost_tracks"].items():
        if age < _MAX_LOST_FRAMES:
            prev_boxes.append(box)
            prev_ids.append(tid)

    if not prev_boxes:
        # Primeiro frame ou estado vazio: todas as boxes são novas
        ids = list(range(len(boxes)))
        _tracker_state["next_id"] = len(boxes)
        _tracker_state["previous_boxes"] = boxes
        _tracker_state["previous_ids"] = ids
        _tracker_state["lost_tracks"] = {}
        return ids

    n_curr = len(boxes)
    n_prev = len(prev_boxes)

    # Matriz de IoU
    pairs: list[tuple[int, int, float]] = []
    for i in range(n_curr):
        for j in range(n_prev):
            iou = _box_iou(boxes[i], prev_boxes[j])
            if iou >= _IOU_THRESHOLD:
                pairs.append((i, j, iou))

    # Matching guloso (maior IoU primeiro)
    pairs.sort(key=lambda x: x[2], reverse=True)
    matched_curr: set[int] = set()
    matched_prev: set[int] = set()
    assignments: dict[int, int] = {}

    for i, j, iou in pairs:
        if i not in matched_curr and j not in matched_prev:
            assignments[i] = prev_ids[j]
            matched_curr.add(i)
            matched_prev.add(j)

    # Atribui novos IDs às boxes não emparelhadas
    ids: list[int] = []
    for i in range(n_curr):
        if i in assignments:
            ids.append(assignments[i])
        else:
            ids.append(_tracker_state["next_id"])
            _tracker_state["next_id"] += 1

    # Atualiza estado do tracker
    _tracker_state["previous_boxes"] = boxes
    _tracker_state["previous_ids"] = ids

    # Tracks que existiam mas não foram emparelhados → lost_tracks
    new_lost: dict = {}
    for j, (box, pid) in enumerate(zip(prev_boxes, prev_ids)):
        if j not in matched_prev and pid not in [assignments.get(i) for i in assignments]:
            # Incrementa idade se já estava perdido
            old_age = _tracker_state["lost_tracks"].get(pid, (box, 0))[1]
            new_lost[pid] = (box, old_age + 1)

    _tracker_state["lost_tracks"] = new_lost

    return ids


# --------------------------------------------------------------------------- #
# Deteção de bounding boxes de pessoas (backend-agnóstico)
# --------------------------------------------------------------------------- #
def _all_person_boxes(
    image: "cv2.Mat",  # type: ignore[valid-type]
) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """Todas as bounding boxes de pessoas (COCO classe 0) no frame + track_ids.

    Devolve ``(boxes, track_ids)`` onde:
    - ``boxes``: lista de ``(x1, y1, x2, y2)`` em coordenadas absolutas.
    - ``track_ids``: lista de IDs persistentes alinhada com ``boxes``.
    - Ambas as listas são vazias se nenhum detector estiver disponível.
    """
    backend, detector = _get_detector()
    if detector is None:
        return [], []

    if backend == "nas":
        return _boxes_from_yolo_nas(image, detector)
    elif backend == "nas_onnx":
        return _boxes_from_yolo_nas_onnx(image, detector)
    else:
        return _boxes_from_yolov8(image, detector)


def _validate_box(
    x1: float, y1: float, x2: float, y2: float, frame_w: int, frame_h: int,
) -> bool:
    """Filtro de tamanho mínimo de bounding box (POSE-22).

    Descarta deteções demasiado pequenas para serem pessoas reais —
    elimina falsos positivos em sombras de móveis, impressoras e objetos de fundo.
    """
    bw, bh = x2 - x1, y2 - y1
    if bw < _MIN_BOX_WIDTH or bh < _MIN_BOX_HEIGHT:
        return False
    area = bw * bh
    if area < _MIN_BOX_PIXEL_AREA:
        return False
    if area < frame_w * frame_h * _MIN_BOX_AREA_RATIO:
        return False
    return True


def _boxes_from_yolov8(
    image: "cv2.Mat", yolo: "YOLO",  # type: ignore[valid-type,name-defined]
) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """Extrai bounding boxes de pessoas via YOLOv8 + ByteTrack nativo.

    Usa ``yolo.track()`` com ByteTrack integrado do Ultralytics em vez do
    rastreador IoU manual. O ByteTrack é imune a trocas de ID em objetos
    estáticos de fundo (móveis, cadeiras) — uma cadeira parada nunca gera
    um track ID estável.

    O parâmetro ``persist=True`` mantém os tracks entre chamadas consecutivas
    (o estado fica no modelo YOLO). O rastreador manual (_assign_track_ids)
    serve apenas como fallback quando o ByteTrack não devolve IDs.
    """
    h, w = image.shape[:2]
    results = yolo.track(
        image,
        persist=True,
        conf=_DETECTION_CONFIDENCE,
        classes=[0],
        tracker="bytetrack.yaml",
        verbose=False,
    )
    boxes_raw = results[0].boxes
    if boxes_raw is None or len(boxes_raw) == 0:
        _assign_track_ids([])
        return [], []

    # Extrai coordenadas e track IDs do ByteTrack
    boxes: list[tuple[int, int, int, int]] = []
    track_ids: list[int] = []

    for i, b in enumerate(boxes_raw):
        x1, y1, x2, y2 = (
            int(b.xyxy[0][0]), int(b.xyxy[0][1]),
            int(b.xyxy[0][2]), int(b.xyxy[0][3]),
        )

        # Filtro de tamanho mínimo (POSE-22)
        if not _validate_box(x1, y1, x2, y2, w, h):
            log.debug("bbox ignorada (tamanho insuficiente): %d,%d,%d,%d", x1, y1, x2, y2)
            continue

        boxes.append((x1, y1, x2, y2))

        # ID do ByteTrack (int) ou fallback para ID posicional
        if boxes_raw.id is not None and i < len(boxes_raw.id):
            track_ids.append(int(boxes_raw.id[i].item()))
        else:
            track_ids.append(i)

    if not boxes:
        _assign_track_ids([])
        return [], []

    return boxes, track_ids


def _boxes_from_yolo_nas(
    image: "cv2.Mat", model,  # type: ignore[valid-type]
) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """Extrai bounding boxes de pessoas via YOLO-NAS + tracking.

    Converte BGR (OpenCV) → RGB (esperado pelo SuperGradients) e filtra
    pela classe ``person`` (COCO índice 0). Aplica filtro de confiança
    elevada e tamanho mínimo de bbox (POSE-22).
    """
    h, w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    try:
        predictions = model.predict(rgb, conf=_DETECTION_CONFIDENCE, fuse_model=False)
    except Exception:
        # Fallback: algumas versões do SG não aceitam fuse_model
        try:
            predictions = model.predict(rgb, conf=_DETECTION_CONFIDENCE)
        except Exception as exc:
            log.warning("YOLO-NAS predict falhou: %s", exc)
            return [], []

    if predictions is None or len(predictions) == 0:
        _assign_track_ids([])
        return [], []

    # predictions pode ser lista de ImagesPredictions ou objeto único
    pred_list = predictions if isinstance(predictions, list) else [predictions]

    boxes: list[tuple[int, int, int, int]] = []
    for pred in pred_list:
        # Navega a estrutura de ImagesPredictions (robusto a variações de versão)
        try:
            detection = getattr(pred, "prediction", pred)
            bboxes = getattr(detection, "bboxes_xyxy", None)
            confs = getattr(detection, "confidence", None)
            labels = getattr(detection, "labels", None)

            if bboxes is None or len(bboxes) == 0:
                continue

            # Filtra classe "person" (COCO índice 0)
            for i in range(len(bboxes)):
                label = int(labels[i]) if labels is not None else -1
                conf = float(confs[i]) if confs is not None else 1.0
                if label == 0 and conf >= _DETECTION_CONFIDENCE:  # person class
                    x1, y1, x2, y2 = bboxes[i]
                    if not _validate_box(x1, y1, x2, y2, w, h):
                        continue
                    boxes.append((int(x1), int(y1), int(x2), int(y2)))
        except Exception as exc:
            log.debug("erro ao extrair boxes do YOLO-NAS: %s", exc)
            continue

    track_ids = _assign_track_ids(boxes)
    return boxes, track_ids


def _boxes_from_yolo_nas_onnx(
    image: "cv2.Mat", session,  # type: ignore[valid-type]
) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """Extrai bounding boxes de pessoas via YOLO-NAS ONNX + IoU tracking.

    O modelo ONNX (Axelera AI / Deci) devolve outputs brutos:
    - ``output``: boxes decodificados em xyxy no espaço 640×640, shape (1, 8400, 4).
    - ``973``: scores por classe (já com sigmoid), shape (1, 8400, 80).

    Aplica filtro de confiança (_DETECTION_CONFIDENCE=0.45), NMS e validação
    de tamanho mínimo de bbox (POSE-22). O tracking é feito via IoU manual
    (_assign_track_ids) porque o ONNX não tem ByteTrack integrado.
    """
    h, w = image.shape[:2]

    # Letterbox resize: mantém rácio, preenche com cinza (114)
    scale = min(_ONNX_INPUT_SIZE[0] / w, _ONNX_INPUT_SIZE[1] / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.full(
        (_ONNX_INPUT_SIZE[1], _ONNX_INPUT_SIZE[0], 3), 114, dtype=np.uint8,
    )
    pad_y = (_ONNX_INPUT_SIZE[1] - new_h) // 2
    pad_x = (_ONNX_INPUT_SIZE[0] - new_w) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    # BGR → RGB + normalização [0, 1] + HWC → CHW + batch
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    input_tensor = np.asarray(rgb, dtype=np.float32) / 255.0
    input_tensor = np.transpose(input_tensor, (2, 0, 1))
    input_tensor = np.expand_dims(input_tensor, axis=0)

    # Inferência ONNX
    input_name = session.get_inputs()[0].name
    try:
        outputs = session.run(None, {input_name: input_tensor})
    except Exception as exc:
        log.warning("YOLO-NAS ONNX inferência falhou: %s", exc)
        _assign_track_ids([])
        return [], []

    if not outputs or len(outputs) < 2:
        _assign_track_ids([])
        return [], []

    # outputs[0]: boxes xyxy no espaço 640×640, shape (1, 8400, 4)
    # outputs[1]: scores por classe, shape (1, 8400, 80)
    boxes_raw = outputs[0][0]    # (8400, 4)
    scores_raw = outputs[1][0]   # (8400, 80)

    # Scores da classe "person" (COCO índice 0)
    person_scores = scores_raw[:, 0]  # (8400,)

    # Filtro de confiança (POSE-22: 0.25 → 0.45)
    mask = person_scores > _DETECTION_CONFIDENCE
    if not mask.any():
        _assign_track_ids([])
        return [], []

    filtered_boxes = boxes_raw[mask]   # (M, 4)
    filtered_scores = person_scores[mask]  # (M,)

    # NMS (Non-Maximum Suppression) — elimina deteções duplicadas
    nms_indices = cv2.dnn.NMSBoxes(
        bboxes=filtered_boxes.tolist(),
        scores=filtered_scores.tolist(),
        score_threshold=_DETECTION_CONFIDENCE,
        nms_threshold=0.5,
    )
    if len(nms_indices) == 0:
        _assign_track_ids([])
        return [], []

    # Converte índices para flat list (cv2.dnn.NMSBoxes devolve (N,1) ou (N,) )
    if nms_indices.ndim == 2:
        nms_indices = nms_indices.flatten()

    final_boxes: list[tuple[int, int, int, int]] = []
    for idx in nms_indices:
        x1_lb, y1_lb, x2_lb, y2_lb = filtered_boxes[int(idx)]

        # Desfaz letterbox: coordenadas 640×640 → frame original
        x1 = (x1_lb - pad_x) / scale
        y1 = (y1_lb - pad_y) / scale
        x2 = (x2_lb - pad_x) / scale
        y2 = (y2_lb - pad_y) / scale

        # Clampa aos limites do frame
        x1 = max(0.0, min(float(w), x1))
        y1 = max(0.0, min(float(h), y1))
        x2 = max(0.0, min(float(w), x2))
        y2 = max(0.0, min(float(h), y2))

        # Filtro de tamanho mínimo (POSE-22)
        if not _validate_box(x1, y1, x2, y2, w, h):
            log.debug("bbox ONNX ignorada (tamanho insuficiente): %.0f,%.0f,%.0f,%.0f",
                      x1, y1, x2, y2)
            continue

        if x2 > x1 and y2 > y1:
            final_boxes.append((int(x1), int(y1), int(x2), int(y2)))

    track_ids = _assign_track_ids(final_boxes)
    return final_boxes, track_ids


# --------------------------------------------------------------------------- #
# MediaPipe Pose Landmarker
# --------------------------------------------------------------------------- #
def ensure_pose_model(cache_dir: Path) -> Path:
    """Baixa o modelo ``.task`` sob demanda; idempotente (checa antes de baixar).

    Mesmo princípio de cache de ``yolov8n.pt`` do ultralytics: uma segunda chamada
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
        raise RuntimeError(
            f"falha ao baixar o modelo de pose de {_MODEL_URL}: {exc}"
        ) from exc

    return model_path


def create_landmarker(model_path: Path, num_poses: int = 3) -> vision.PoseLandmarker:
    """Cria o ``PoseLandmarker`` (Task API) a partir do modelo já em cache.

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


# --------------------------------------------------------------------------- #
# Extração de keypoints multi-pessoa com tracking
# --------------------------------------------------------------------------- #
def extract_all_keypoints(
    frame_path: Path, landmarker: vision.PoseLandmarker
) -> list[PoseFrame]:
    """YOLO multi-crop → MediaPipe por pessoa → coordenadas normalizadas + track_id.

    Para cada pessoa detetada pelo YOLO (COCO classe 0, conf ≥ 0.25):
    1. Recorta a região com 20% de padding
    2. Executa o MediaPipe apenas nessa região
    3. Mapeia as coordenadas de volta para o frame completo
    4. Atribui o ``track_id`` persistente (IoU tracker) ao ``PoseFrame``

    Com YOLO, o MediaPipe não vê objetos de fundo (mesas, computadores)
    e ganha resolução efetiva para pessoas distantes. Se o YOLO não
    encontrar ninguém, faz fallback para o frame inteiro (track_id=None).

    Devolve lista vazia se nenhuma pessoa for detetada.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise FileNotFoundError(f"frame ilegível: {frame_path}")
    h, w = frame.shape[:2]

    boxes, track_ids = _all_person_boxes(frame)
    all_poses: list[PoseFrame] = []

    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        track_id = track_ids[idx] if idx < len(track_ids) else None

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
                    (
                        (lm.x * cw + cx1) / w,
                        (lm.y * ch + cy1) / h,
                        lm.z,
                        lm.visibility,
                    )
                    for lm in pose_landmarks
                ]
                all_poses.append(PoseFrame(landmarks=landmarks, track_id=track_id))

    if all_poses:
        return all_poses

    # Fallback: YOLO não encontrou pessoas → frame inteiro (sem track_id)
    _assign_track_ids([])
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if not result.pose_landmarks:
        return []

    return [
        PoseFrame(
            landmarks=[(lm.x, lm.y, lm.z, lm.visibility) for lm in pose_landmarks],
            track_id=None,
        )
        for pose_landmarks in result.pose_landmarks
    ]


def extract_keypoints(
    frame_path: Path, landmarker: vision.PoseLandmarker
) -> PoseFrame | None:
    """Wrapper retrocompatível: devolve o primeiro esqueleto ou ``None``.

    Delegar a ``extract_all_keypoints`` mantém a semântica original (1 pessoa =
    primeiro elemento; 0 pessoas = ``None``) sem duplicar a lógica de inferência.
    """
    all_poses = extract_all_keypoints(frame_path, landmarker)
    return all_poses[0] if all_poses else None
