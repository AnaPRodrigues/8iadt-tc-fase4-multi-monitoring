"""Testes do armazenamento local de arquivos enviados."""

import pytest

from app import armazenamento


@pytest.fixture(autouse=True)
def _uploads_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_UPLOADS_DIR", str(tmp_path / "uploads"))


def test_salvar_arquivo_grava_sob_paciente_e_modalidade():
    caminho = armazenamento.salvar_arquivo("p-1", "documento", "receita.pdf", b"conteudo")

    assert caminho.read_bytes() == b"conteudo"
    assert caminho.parent.name == "documento"
    assert caminho.parent.parent.name == "p-1"


def test_salvar_arquivo_nao_sobrescreve_nome_repetido():
    a = armazenamento.salvar_arquivo("p-1", "audio", "a.wav", b"um")
    b = armazenamento.salvar_arquivo("p-1", "audio", "a.wav", b"dois")

    assert a != b
    assert a.read_bytes() == b"um"
    assert b.read_bytes() == b"dois"


def test_nome_original_com_separadores_e_neutralizado():
    caminho = armazenamento.salvar_arquivo("p-1", "documento", "../../etc/passwd", b"x")

    assert caminho.parent.parent.name == "p-1"
    assert "/" not in caminho.name
    assert ".." not in caminho.name
