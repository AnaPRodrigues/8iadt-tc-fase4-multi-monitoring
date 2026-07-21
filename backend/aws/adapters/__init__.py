"""Interfaces e modelos de dados para os adapters de IA gerenciada (AD-035).

`TextExtractor`/`ImageAnalyzer` isolam Textract/Rekognition (cloud) e as
implementações OSS locais (Tesseract/YOLOv8, registradas por F4/F1) atrás de
um único contrato. Pipelines dependem só da interface.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ExtractedText:
    lines: list[str]
    raw: dict


@dataclass(frozen=True)
class ImageLabel:
    name: str
    confidence: float


@dataclass(frozen=True)
class ImageAnalysis:
    labels: list[ImageLabel]
    raw: dict


@runtime_checkable
class TextExtractor(Protocol):
    def extract(self, pdf_bytes: bytes) -> ExtractedText: ...


@runtime_checkable
class ImageAnalyzer(Protocol):
    def analyze(self, image_bytes: bytes) -> ImageAnalysis: ...
