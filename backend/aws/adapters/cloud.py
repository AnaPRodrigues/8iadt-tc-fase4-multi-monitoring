"""Implementações de nuvem dos adaptadores — Amazon Textract e Rekognition.

Usam as APIs **síncronas com bytes embutidos**: o arquivo local vai direto na
chamada (`Document={'Bytes': ...}` / `Image={'Bytes': ...}`) e a resposta volta
para o processamento local, sem bucket intermediário.

O parsing de domínio (campos de prescrição, estruturas cirúrgicas) fica com os
pipelines que consomem `.raw`; aqui só se traduz a resposta do serviço para o
contrato comum (`ExtractedText` / `ImageAnalysis`).
"""

import time
from typing import Any

from aws.adapters import (
    ExtractedText,
    ImageAnalysis,
    ImageLabel,
    register_image_analyzer,
    register_text_extractor,
)
from aws.clients import get_client
from common import atividade


def _request_id(response: dict) -> str:
    return response.get("ResponseMetadata", {}).get("RequestId", "—")


class TextractExtractor:
    """Extração de texto/campos de documento via Amazon Textract (`analyze_document`)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        atividade.nuvem_chamando(
            "documento", "Textract", "analyze_document", f"documento ({len(pdf_bytes)} bytes)"
        )
        inicio = time.monotonic()
        response = self._client.analyze_document(
            Document={"Bytes": pdf_bytes},
            FeatureTypes=["FORMS"],
        )
        duracao = time.monotonic() - inicio
        blocos = response.get("Blocks", [])
        atividade.nuvem_concluida(
            "documento", f"{len(blocos)} blocos extraídos", duracao, _request_id(response)
        )
        lines = [b["Text"] for b in blocos if b.get("BlockType") == "LINE"]
        return ExtractedText(lines=lines, raw=response)


class RekognitionAnalyzer:
    """Rótulos de objetos em imagem via Amazon Rekognition (`detect_labels`)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        atividade.nuvem_chamando(
            "video", "Rekognition", "detect_labels", f"imagem ({len(image_bytes)} bytes)"
        )
        inicio = time.monotonic()
        response = self._client.detect_labels(Image={"Bytes": image_bytes})
        duracao = time.monotonic() - inicio
        rotulos = response.get("Labels", [])
        atividade.nuvem_concluida(
            "video", f"{len(rotulos)} rótulos reconhecidos", duracao, _request_id(response)
        )
        labels = [ImageLabel(name=lbl["Name"], confidence=lbl["Confidence"]) for lbl in rotulos]
        return ImageAnalysis(labels=labels, raw=response)


def register_cloud_adapters() -> None:
    """Registra as implementações de nuvem para o modo `aws`.

    As implementações locais (pdfplumber, YOLOv8) são registradas pelos pipelines
    de prescrição e vídeo — este módulo não as conhece.
    """
    register_text_extractor("aws", lambda: TextractExtractor(get_client("textract")))
    register_image_analyzer("aws", lambda: RekognitionAnalyzer(get_client("rekognition")))
