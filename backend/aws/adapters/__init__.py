"""Interfaces e modelos de dados para os adapters de IA gerenciada (AD-035).

`TextExtractor`/`ImageAnalyzer` isolam Textract/Rekognition (cloud) e as
implementações OSS locais (Tesseract/YOLOv8, registradas por F4/F1) atrás de
um único contrato. Pipelines dependem só da interface.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aws.clients import load_aws_config


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


# Registro por ENV (AWSF-05). A fundação registra as implementações CLOUD
# (ver adapters/cloud.py); LOCAL é registrado por F4/F1 quando forem construídas.
_TEXT_EXTRACTORS: dict[str, Callable[[], TextExtractor]] = {}
_IMAGE_ANALYZERS: dict[str, Callable[[], ImageAnalyzer]] = {}


def register_text_extractor(env: str, factory: Callable[[], TextExtractor]) -> None:
    _TEXT_EXTRACTORS[env] = factory


def register_image_analyzer(env: str, factory: Callable[[], ImageAnalyzer]) -> None:
    _IMAGE_ANALYZERS[env] = factory


def get_text_extractor(env: str | None = None) -> TextExtractor:
    env = env or load_aws_config().env
    try:
        factory = _TEXT_EXTRACTORS[env]
    except KeyError:
        raise ValueError(f"nenhum TextExtractor registrado para ENV={env!r}") from None
    return factory()


def get_image_analyzer(env: str | None = None) -> ImageAnalyzer:
    env = env or load_aws_config().env
    try:
        factory = _IMAGE_ANALYZERS[env]
    except KeyError:
        raise ValueError(f"nenhum ImageAnalyzer registrado para ENV={env!r}") from None
    return factory()
