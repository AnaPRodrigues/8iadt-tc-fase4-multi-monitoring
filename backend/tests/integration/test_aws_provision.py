"""Testes de integração de provision.py contra LocalStack real (AD-038, AWSF-06).

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566, em vez de falhar a suíte inteira em máquinas sem Docker.
"""

import socket
import uuid

import pytest

from aws.clients import get_client
from aws.provision import ensure_bucket, ensure_table, ensure_topic


def _localstack_disponivel() -> bool:
    try:
        with socket.create_connection(("localhost", 4566), timeout=2):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _localstack_disponivel(),
        reason="LocalStack não está de pé em :4566 — rode `make localstack-up`",
    ),
]


@pytest.fixture(autouse=True)
def _env_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


def _nome_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


# ---------- ensure_bucket ----------


def test_ensure_bucket_cria_quando_ausente():
    nome = _nome_unico("mm-test-bucket")

    result = ensure_bucket(nome)

    assert result.created is True
    assert result.resource == nome
    get_client("s3").head_bucket(Bucket=nome)  # não lança = bucket existe de fato


def test_ensure_bucket_segunda_chamada_nao_recria():
    nome = _nome_unico("mm-test-bucket")

    primeira = ensure_bucket(nome)
    segunda = ensure_bucket(nome)

    assert primeira.created is True
    assert segunda.created is False


# ---------- ensure_topic ----------


def test_ensure_topic_cria_quando_ausente():
    nome = _nome_unico("mm-test-topic")

    result = ensure_topic(nome)

    assert result.created is True
    arns = [
        t["TopicArn"]
        for page in get_client("sns").get_paginator("list_topics").paginate()
        for t in page["Topics"]
    ]
    assert any(arn.endswith(f":{nome}") for arn in arns)


def test_ensure_topic_segunda_chamada_nao_recria():
    nome = _nome_unico("mm-test-topic")

    primeira = ensure_topic(nome)
    segunda = ensure_topic(nome)

    assert primeira.created is True
    assert segunda.created is False


# ---------- ensure_table ----------


def test_ensure_table_cria_quando_ausente():
    nome = _nome_unico("mm-test-table")

    result = ensure_table(nome)

    assert result.created is True
    desc = get_client("dynamodb").describe_table(TableName=nome)
    assert desc["Table"]["TableStatus"] in ("ACTIVE", "CREATING")


def test_ensure_table_segunda_chamada_nao_recria():
    nome = _nome_unico("mm-test-table")

    primeira = ensure_table(nome)
    segunda = ensure_table(nome)

    assert primeira.created is True
    assert segunda.created is False
