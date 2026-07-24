"""Caminho de nuvem com o cliente do SDK substituído por um dublê.

Prova, sem credencial nem rede, que:
- Textract é chamado por `analyze_document` com os bytes embutidos (`Document={'Bytes': ...}`);
- Rekognition é chamado por `detect_labels` com os bytes embutidos (`Image={'Bytes': ...}`);
- a resposta do serviço é traduzida corretamente para o contrato comum.
"""

from aws.adapters import get_image_analyzer, get_text_extractor
from aws.adapters.cloud import RekognitionAnalyzer, TextractExtractor, register_cloud_adapters


class _TextractClientFake:
    def __init__(self):
        self.chamada = None

    def analyze_document(self, **kwargs):
        self.chamada = kwargs
        return {
            "Blocks": [
                {"BlockType": "LINE", "Text": "Paciente: p-1"},
                {"BlockType": "LINE", "Text": "Medicamento: losartana"},
                {"BlockType": "WORD", "Text": "ignorado"},
            ]
        }


class _RekognitionClientFake:
    def __init__(self):
        self.chamada = None

    def detect_labels(self, **kwargs):
        self.chamada = kwargs
        return {"Labels": [{"Name": "Person", "Confidence": 98.5}]}


def test_textract_usa_analyze_document_com_bytes_embutidos():
    cliente = _TextractClientFake()

    resultado = TextractExtractor(cliente).extract(b"%PDF-conteudo")

    # chamada síncrona com bytes embutidos, sem bucket
    assert cliente.chamada["Document"] == {"Bytes": b"%PDF-conteudo"}
    assert "FeatureTypes" in cliente.chamada
    # só as linhas (LINE) viram texto; WORD é ignorado
    assert resultado.lines == ["Paciente: p-1", "Medicamento: losartana"]


def test_rekognition_usa_detect_labels_com_bytes_embutidos():
    cliente = _RekognitionClientFake()

    resultado = RekognitionAnalyzer(cliente).analyze(b"\xff\xd8imagem")

    assert cliente.chamada["Image"] == {"Bytes": b"\xff\xd8imagem"}
    assert len(resultado.labels) == 1
    assert resultado.labels[0].name == "Person"
    assert resultado.labels[0].confidence == 98.5


def test_register_cloud_adapters_resolve_textract_e_rekognition_para_o_modo_aws(monkeypatch):
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    register_cloud_adapters()

    assert isinstance(get_text_extractor("aws"), TextractExtractor)
    assert isinstance(get_image_analyzer("aws"), RekognitionAnalyzer)
