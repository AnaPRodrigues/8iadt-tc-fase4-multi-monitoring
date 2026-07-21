"""Testes dos modelos de dados e interfaces TextExtractor/ImageAnalyzer (AWSF-04)."""

import pytest

from aws.adapters import ExtractedText, ImageAnalysis, ImageAnalyzer, ImageLabel, TextExtractor


def test_extracted_text_e_imutavel():
    t = ExtractedText(lines=["a", "b"], raw={"x": 1})

    assert t.lines == ["a", "b"]
    with pytest.raises(AttributeError):
        t.lines = ["c"]


def test_image_label_guarda_nome_e_confianca():
    label = ImageLabel(name="Bisturi", confidence=97.5)

    assert label.name == "Bisturi"
    assert label.confidence == 97.5
    with pytest.raises(AttributeError):
        label.confidence = 0.0


def test_image_analysis_guarda_labels_e_raw_e_e_imutavel():
    analysis = ImageAnalysis(labels=[ImageLabel("X", 90.0)], raw={"Labels": []})

    assert len(analysis.labels) == 1
    assert analysis.raw == {"Labels": []}
    with pytest.raises(AttributeError):
        analysis.raw = {}


class _TextExtractorFake:
    def extract(self, pdf_bytes: bytes) -> ExtractedText:
        return ExtractedText(lines=[], raw={})


class _ImageAnalyzerFake:
    def analyze(self, image_bytes: bytes) -> ImageAnalysis:
        return ImageAnalysis(labels=[], raw={})


def test_objeto_duck_typed_satisfaz_o_protocol_text_extractor():
    assert isinstance(_TextExtractorFake(), TextExtractor)


def test_objeto_duck_typed_satisfaz_o_protocol_image_analyzer():
    assert isinstance(_ImageAnalyzerFake(), ImageAnalyzer)


def test_objeto_sem_o_metodo_nao_satisfaz_o_protocol():
    class _SemMetodo:
        pass

    assert not isinstance(_SemMetodo(), TextExtractor)
    assert not isinstance(_SemMetodo(), ImageAnalyzer)
