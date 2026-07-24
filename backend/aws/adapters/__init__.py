"""Contrato dos adaptadores de extração de texto e de análise de imagem.

Cada capacidade tem uma interface (`TextExtractor`, `ImageAnalyzer`) e duas
implementações, escolhidas pela variável de ambiente `ENV`:

- `local`: bibliotecas/modelos que rodam na própria máquina (pdfplumber para PDF,
  YOLOv8 para imagem) — registradas pelos pipelines de prescrição e vídeo.
- `aws`: serviços gerenciados (Textract, Rekognition) — registradas em
  `aws/adapters/cloud.py`.

Os pipelines dependem só da interface; a seleção da implementação é feita por `ENV`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from aws.clients import resolve_env


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


# Registro por modo (`local` / `aws`). As implementações locais são registradas
# pelos pipelines de prescrição e vídeo; as de nuvem, por `aws/adapters/cloud.py`.
_TEXT_EXTRACTORS: dict[str, Callable[[], TextExtractor]] = {}
_IMAGE_ANALYZERS: dict[str, Callable[[], ImageAnalyzer]] = {}


def register_text_extractor(env: str, factory: Callable[[], TextExtractor]) -> None:
    _TEXT_EXTRACTORS[env] = factory


def register_image_analyzer(env: str, factory: Callable[[], ImageAnalyzer]) -> None:
    _IMAGE_ANALYZERS[env] = factory


def get_text_extractor(env: str | None = None) -> TextExtractor:
    env = env or resolve_env()
    try:
        factory = _TEXT_EXTRACTORS[env]
    except KeyError:
        raise ValueError(f"nenhum extrator de texto registrado para o modo {env!r}") from None
    return factory()


def get_image_analyzer(env: str | None = None) -> ImageAnalyzer:
    env = env or resolve_env()
    try:
        factory = _IMAGE_ANALYZERS[env]
    except KeyError:
        raise ValueError(f"nenhum analisador de imagem registrado para o modo {env!r}") from None
    return factory()
