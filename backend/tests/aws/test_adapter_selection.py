"""Seleção de adaptador por modo (`ENV`): `local` escolhe a implementação local,
`aws` escolhe a de nuvem. Nenhuma chamada de rede -- só resolução do registro.
"""

import pytest

from aws.adapters import (
    ExtractedText,
    ImageAnalysis,
    get_image_analyzer,
    get_text_extractor,
    register_image_analyzer,
    register_text_extractor,
)


class _ExtratorLocalFake:
    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        return ExtractedText(lines=["local"], raw={})


class _ExtratorNuvemFake:
    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        return ExtractedText(lines=["aws"], raw={})


class _AnalisadorLocalFake:
    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        return ImageAnalysis(labels=[], raw={"origem": "local"})


class _AnalisadorNuvemFake:
    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        return ImageAnalysis(labels=[], raw={"origem": "aws"})


@pytest.fixture(autouse=True)
def _registra_os_dois():
    register_text_extractor("local", _ExtratorLocalFake)
    register_text_extractor("aws", _ExtratorNuvemFake)
    register_image_analyzer("local", _AnalisadorLocalFake)
    register_image_analyzer("aws", _AnalisadorNuvemFake)


def test_modo_local_escolhe_o_extrator_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")

    assert get_text_extractor().extract(b"x").lines == ["local"]


def test_modo_aws_escolhe_o_extrator_de_nuvem(monkeypatch):
    monkeypatch.setenv("ENV", "aws")

    assert get_text_extractor().extract(b"x").lines == ["aws"]


def test_modo_local_escolhe_o_analisador_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")

    assert get_image_analyzer().analyze(b"x").raw["origem"] == "local"


def test_modo_aws_escolhe_o_analisador_de_nuvem(monkeypatch):
    monkeypatch.setenv("ENV", "aws")

    assert get_image_analyzer().analyze(b"x").raw["origem"] == "aws"


def test_env_ausente_resolve_como_local(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)

    assert get_text_extractor().extract(b"x").lines == ["local"]


def test_modo_sem_implementacao_registrada_falha_com_mensagem_clara(monkeypatch):
    from aws import adapters

    monkeypatch.setattr(adapters, "_TEXT_EXTRACTORS", {})

    with pytest.raises(ValueError, match="local"):
        get_text_extractor("local")
