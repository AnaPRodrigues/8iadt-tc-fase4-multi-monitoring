"""Testes de RekognitionAnalyzer e do registro dos adapters cloud."""

from aws.adapters import get_image_analyzer, get_text_extractor
from aws.adapters.cloud import RekognitionAnalyzer, TextractExtractor, register_cloud_adapters


class _FakeRekognitionClient:
    def __init__(self, labels):
        self._labels = labels
        self.calls = []

    def detect_labels(self, Image):
        self.calls.append(Image)
        return {"Labels": self._labels}


def test_mapeia_labels_da_resposta():
    labels = [
        {"Name": "Bisturi", "Confidence": 98.2},
        {"Name": "Pinça", "Confidence": 76.5},
    ]
    client = _FakeRekognitionClient(labels)

    result = RekognitionAnalyzer(client).analyze(b"frame")

    assert [lbl.name for lbl in result.labels] == ["Bisturi", "Pinça"]
    assert [lbl.confidence for lbl in result.labels] == [98.2, 76.5]


def test_resposta_sem_labels_produz_lista_vazia():
    client = _FakeRekognitionClient([])

    result = RekognitionAnalyzer(client).analyze(b"frame")

    assert result.labels == []


def test_raw_preserva_a_resposta_completa():
    labels = [{"Name": "X", "Confidence": 50.0}]
    client = _FakeRekognitionClient(labels)

    result = RekognitionAnalyzer(client).analyze(b"frame")

    assert result.raw == {"Labels": labels}


def test_chama_detect_labels_com_os_bytes_da_imagem():
    client = _FakeRekognitionClient([])

    RekognitionAnalyzer(client).analyze(b"bytes-do-frame")

    assert client.calls == [{"Bytes": b"bytes-do-frame"}]


def test_register_cloud_adapters_resolve_textract_e_rekognition_para_cloud(monkeypatch):
    monkeypatch.setenv("ENV", "cloud")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    register_cloud_adapters()

    assert isinstance(get_text_extractor("cloud"), TextractExtractor)
    assert isinstance(get_image_analyzer("cloud"), RekognitionAnalyzer)
