"""Implementações cloud dos adapters — wrappers finos sobre Textract/Rekognition.

Parsing de domínio (campos de prescrição, instrumentos cirúrgicos) fica com as
features que consomem `.raw`; aqui só se traduz a resposta do provedor para o
contrato comum (`ExtractedText`/`ImageAnalysis`).
"""

from typing import Any

from aws.adapters import ExtractedText


class TextractExtractor:
    """`TextExtractor` via AWS Textract (AD-035)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        response = self._client.detect_document_text(Document={"Bytes": pdf_bytes})
        lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return ExtractedText(lines=lines, raw=response)
