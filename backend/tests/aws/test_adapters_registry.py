"""Testes do registro/resolução de adapters por ENV."""

import pytest

from aws.adapters import (
    ExtractedText,
    ImageAnalysis,
    get_image_analyzer,
    get_text_extractor,
    register_image_analyzer,
    register_text_extractor,
)


class _FakeLocalExtractor:
    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        return ExtractedText(lines=["local"], raw={})


class _FakeCloudExtractor:
    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        return ExtractedText(lines=["cloud"], raw={})


class _FakeAnalyzer:
    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        return ImageAnalysis(labels=[], raw={})


def test_registra_e_resolve_text_extractor_por_env():
    register_text_extractor("local", _FakeLocalExtractor)
    register_text_extractor("cloud", _FakeCloudExtractor)

    local = get_text_extractor("local")
    cloud = get_text_extractor("cloud")

    assert isinstance(local, _FakeLocalExtractor)
    assert isinstance(cloud, _FakeCloudExtractor)
    assert local.extract(b"").lines == ["local"]
    assert cloud.extract(b"").lines == ["cloud"]


def test_env_sem_text_extractor_registrado_levanta_erro():
    with pytest.raises(ValueError, match="local"):
        get_text_extractor("local")


def test_registra_e_resolve_image_analyzer_por_env():
    register_image_analyzer("cloud", _FakeAnalyzer)

    analyzer = get_image_analyzer("cloud")

    assert isinstance(analyzer, _FakeAnalyzer)


def test_env_sem_image_analyzer_registrado_levanta_erro():
    with pytest.raises(ValueError, match="cloud"):
        get_image_analyzer("cloud")


def test_registro_de_text_extractor_nao_interfere_no_de_image_analyzer():
    register_text_extractor("local", _FakeLocalExtractor)

    with pytest.raises(ValueError):
        get_image_analyzer("local")


def test_get_text_extractor_usa_env_ativo_quando_omitido(monkeypatch):
    monkeypatch.setenv("ENV", "cloud")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    register_text_extractor("cloud", _FakeCloudExtractor)

    extractor = get_text_extractor()

    assert isinstance(extractor, _FakeCloudExtractor)
