"""Implementações de nuvem dos adaptadores — Amazon Textract e Rekognition.

Usam as APIs **síncronas com bytes embutidos**: o arquivo local vai direto na
chamada (`Document={'Bytes': ...}` / `Image={'Bytes': ...}`) e a resposta volta
para o processamento local, sem bucket intermediário.

O parsing de domínio (campos de prescrição, estruturas cirúrgicas) fica com os
pipelines que consomem `.raw`; aqui só se traduz a resposta do serviço para o
contrato comum (`ExtractedText` / `ImageAnalysis`).
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
    """Extração de texto/campos de documento via Amazon Textract (`analyze_document`)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        response = self._client.analyze_document(
            Document={"Bytes": pdf_bytes},
            FeatureTypes=["FORMS"],
        )
        lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return ExtractedText(lines=lines, raw=response)


class RekognitionAnalyzer:
    """Rótulos de objetos em imagem via Amazon Rekognition (`detect_labels`)."""

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
    """Registra as implementações de nuvem para o modo `aws`.

    As implementações locais (pdfplumber, YOLOv8) são registradas pelos pipelines
    de prescrição e vídeo — este módulo não as conhece.
    """
    register_text_extractor("aws", lambda: TextractExtractor(get_client("textract")))
    register_image_analyzer("aws", lambda: RekognitionAnalyzer(get_client("rekognition")))
