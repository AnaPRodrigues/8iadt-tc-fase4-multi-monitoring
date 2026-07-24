"""`TextExtractor` local via `pdfplumber`.

Os PDFs sintéticos gerados por `generator.py` têm texto real embutido — extração
direta é mais rápida/precisa que OCR (Tesseract seria necessário só para imagem
escaneada, que não é o caso aqui).
"""

import io

import pdfplumber

from aws.adapters import ExtractedText, register_text_extractor
from common import atividade


class PdfplumberExtractor:
    """`TextExtractor` local via `pdfplumber`."""

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            text = page.extract_text() or ""
            lines = text.split("\n") if text else []
            raw = {"page_count": len(pdf.pages)}
        atividade.local("documento", f"texto extraído do PDF com pdfplumber — {len(lines)} linhas")
        return ExtractedText(lines=lines, raw=raw)


def register_local_adapters() -> None:
    """Registra `PdfplumberExtractor` para `env="local"`."""
    register_text_extractor("local", lambda: PdfplumberExtractor())
