"""Testes de TextractExtractor. Cliente boto3 fake por
duck-typing — Textract não existe no LocalStack Community."""

from aws.adapters.cloud import TextractExtractor


class _FakeTextractClient:
    def __init__(self, blocks):
        self._blocks = blocks
        self.calls = []

    def detect_document_text(self, Document):
        self.calls.append(Document)
        return {"Blocks": self._blocks}


def test_extrai_apenas_blocos_do_tipo_line_na_ordem():
    blocks = [
        {"BlockType": "PAGE"},
        {"BlockType": "LINE", "Text": "Paracetamol 500mg"},
        {"BlockType": "WORD", "Text": "Paracetamol"},
        {"BlockType": "LINE", "Text": "Tomar a cada 8 horas"},
    ]
    client = _FakeTextractClient(blocks)

    result = TextractExtractor(client).extract(b"conteudo-do-pdf")

    assert result.lines == ["Paracetamol 500mg", "Tomar a cada 8 horas"]


def test_resposta_sem_blocos_line_produz_lista_vazia():
    client = _FakeTextractClient([{"BlockType": "PAGE"}])

    result = TextractExtractor(client).extract(b"x")

    assert result.lines == []


def test_raw_preserva_a_resposta_completa_sem_transformacao():
    blocks = [{"BlockType": "LINE", "Text": "A"}]
    client = _FakeTextractClient(blocks)

    result = TextractExtractor(client).extract(b"x")

    assert result.raw == {"Blocks": blocks}


def test_chama_detect_document_text_com_os_bytes_do_pdf():
    client = _FakeTextractClient([])

    TextractExtractor(client).extract(b"meu-pdf-em-bytes")

    assert client.calls == [{"Bytes": b"meu-pdf-em-bytes"}]
