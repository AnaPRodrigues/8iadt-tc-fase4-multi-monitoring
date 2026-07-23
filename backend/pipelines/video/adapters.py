"""`YoloImageAnalyzer` -- `ImageAnalyzer` local via YOLOv8 fine-tuned.

`YoloDetector.detect` opera sobre `image_path`, não bytes -- o adapter
grava os bytes recebidos num arquivo temporário antes de chamar o detector,
em vez de duplicar esse contrato para também aceitar bytes.
"""

import tempfile
from pathlib import Path

from aws.adapters import ImageAnalysis, ImageLabel, register_image_analyzer
from pipelines.video.object_detector import YoloDetector


class YoloImageAnalyzer:
    """`ImageAnalyzer` local: envolve `YoloDetector`.

    O contrato existente da fundação (`ImageLabel`) não carrega bbox -- só a
    raia local via `object_detector.py` expõe a caixa, quando necessário.
    """

    def __init__(self, weights_path: Path):
        self._detector = YoloDetector(weights_path)

    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            tmp.write(image_bytes)
            tmp.flush()
            detections = self._detector.detect(Path(tmp.name))

        labels = [ImageLabel(name=d.class_name, confidence=d.confidence) for d in detections]
        return ImageAnalysis(labels=labels, raw={"detection_count": len(detections)})


def register_local_adapters(weights_path: Path) -> None:
    """Registra `YoloImageAnalyzer` para `env="local"`."""
    register_image_analyzer("local", lambda: YoloImageAnalyzer(weights_path))
