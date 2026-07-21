"""Implementações cloud dos adapters — wrappers finos sobre Textract/Rekognition.

Parsing de domínio (campos de prescrição, instrumentos cirúrgicos) fica com as
features que consomem `.raw`; aqui só se traduz a resposta do provedor para o
contrato comum (`ExtractedText`/`ImageAnalysis`).
"""

from typing import Any

from aws.adapters import (
    ExtractedText,
    ImageAnalysis,
    ImageLabel,
    register_image_analyzer,
    register_text_extractor,
)
from aws.clients import get_client


class TextractExtractor:
    """`TextExtractor` via AWS Textract (AD-035)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        response = self._client.detect_document_text(Document={"Bytes": pdf_bytes})
        lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return ExtractedText(lines=lines, raw=response)


class RekognitionAnalyzer:
    """`ImageAnalyzer` via AWS Rekognition (AD-035)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        response = self._client.detect_labels(Image={"Bytes": image_bytes})
        labels = [
            ImageLabel(name=lbl["Name"], confidence=lbl["Confidence"])
            for lbl in response.get("Labels", [])
        ]
        return ImageAnalysis(labels=labels, raw=response)


def register_cloud_adapters() -> None:
    """Registra as implementações cloud para `env="cloud"` (AD-035).

    As implementações LOCAL (Tesseract/pdfplumber, YOLOv8) são registradas por
    F4/F1 quando forem construídas — a fundação não as conhece.
    """
    register_text_extractor("cloud", lambda: TextractExtractor(get_client("textract")))
    register_image_analyzer("cloud", lambda: RekognitionAnalyzer(get_client("rekognition")))
