"""Detecção via YOLOv8 fine-tuned + evidência de estrutura crítica.

`YOLO.predict(...)` grava em `runs/detect/predict` por padrão mesmo pela API
Python (`DEFAULT_CFG.save=True`) -- por isso `save=False` é sempre explícito
aqui, mesmo princípio de nunca depender do padrão do ultralytics.
"""

from pathlib import Path

import cv2
from ultralytics import YOLO

from common.evidence import Evidence, evidence_dir, save_evidence
from common.logging import get_logger
from pipelines.video.models import Detection

log = get_logger("video.object_detector")

CRITICAL_STRUCTURES = {"cystic_artery", "cystic_duct", "cystic_plate"}


class YoloDetector:
    """Envolve os pesos fine-tuned para devolver bbox+classe+confiança reais."""

    def __init__(self, weights_path: Path, confidence_threshold: float = 0.25):
        self._model = YOLO(str(weights_path))
        self._confidence_threshold = confidence_threshold

    def detect(self, image_path: Path) -> list[Detection]:
        """Roda a detecção real num frame; lista vazia se nada for detectado."""
        results = self._model.predict(
            str(image_path), conf=self._confidence_threshold, verbose=False, save=False
        )
        if not results or results[0].boxes is None:
            return []

        result = results[0]
        detections = []
        for box in result.boxes:
            class_name = result.names[int(box.cls[0])]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=(x1, y1, x2 - x1, y2 - y1),
                )
            )
        return detections


def draw_detections(image_path: Path, detections: list[Detection], output_path: Path) -> Path:
    """Desenha as caixas detectadas sobre o frame real."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"frame ilegível: {image_path}")

    for detection in detections:
        x, y, width, height = detection.bbox
        cv2.rectangle(
            image, (int(x), int(y)), (int(x + width), int(y + height)), (0, 0, 255), 2
        )
        cv2.putText(
            image,
            detection.class_name,
            (int(x), max(int(y) - 5, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path


def save_critical_structure_evidence(
    *,
    image_path: Path,
    detections: list[Detection],
    run_id: str,
    root: str | Path = "output",
) -> Evidence | None:
    """Gera evidência (frame com caixas + metadados) só se houver estrutura crítica.

    Devolve `None` quando nenhuma detecção é de uma estrutura crítica -- ausência
    de evidência é o resultado esperado, não uma falha.
    """
    critical = [d for d in detections if d.class_name in CRITICAL_STRUCTURES]
    if not critical:
        return None

    dest_dir = evidence_dir("video_object", run_id, root)
    annotated_path = dest_dir / f"{image_path.stem}-critical.png"
    draw_detections(image_path, detections, annotated_path)

    log.info(
        "estrutura crítica detectada em %s: %s",
        image_path.name,
        [d.class_name for d in critical],
    )

    return save_evidence(
        feature="video_object",
        run_id=run_id,
        evidence_id=f"{image_path.stem}-critical",
        source_record_id=image_path.stem,
        artifact_path=annotated_path,
        metadata={
            "detections": [
                {"class_name": d.class_name, "confidence": d.confidence, "bbox": list(d.bbox)}
                for d in critical
            ]
        },
        root=root,
    )
