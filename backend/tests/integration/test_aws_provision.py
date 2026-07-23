"""Testes de integração de provision.py contra LocalStack real.

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566, em vez de falhar a suíte inteira em máquinas sem Docker.
"""

import os
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

from aws.clients import get_client
from aws.provision import ensure_bucket, ensure_table, ensure_topic, main

_REPO_ROOT = Path(__file__).resolve().parents[3]


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


# ---------- main() e make infra-local ----------


def _nomes_unicos():
    return {
        "S3_BUCKET": _nome_unico("mm-test-bucket"),
        "SNS_TOPIC": _nome_unico("mm-test-topic"),
        "DYNAMODB_TABLE": _nome_unico("mm-test-table"),
    }


def test_main_provisiona_os_tres_recursos(monkeypatch):
    nomes = _nomes_unicos()
    for k, v in nomes.items():
        monkeypatch.setenv(k, v)

    rc = main()

    assert rc == 0
    get_client("s3").head_bucket(Bucket=nomes["S3_BUCKET"])
    get_client("dynamodb").describe_table(TableName=nomes["DYNAMODB_TABLE"])


def test_main_e_idempotente_rodando_duas_vezes(monkeypatch):
    nomes = _nomes_unicos()
    for k, v in nomes.items():
        monkeypatch.setenv(k, v)

    assert main() == 0
    assert main() == 0  # segunda vez não falha nem recria


def test_main_falha_com_variavel_ausente(monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setenv("SNS_TOPIC", _nome_unico("mm-test-topic"))
    monkeypatch.setenv("DYNAMODB_TABLE", _nome_unico("mm-test-table"))

    assert main() == 1


def test_main_com_localstack_fora_do_ar_falha_com_mensagem_acionavel(monkeypatch, caplog):
    # Porta fechada em vez do LocalStack real — não derruba o container de verdade.
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:1")
    nomes = _nomes_unicos()
    for k, v in nomes.items():
        monkeypatch.setenv(k, v)

    with caplog.at_level("ERROR", logger="mm.aws.provision"):
        rc = main()

    assert rc == 1
    assert "localstack-up" in caplog.text.lower()


def test_make_infra_local_de_ponta_a_ponta():
    nomes = _nomes_unicos()
    env = {**os.environ, "ENV": "local", **nomes}

    result = subprocess.run(
        ["make", "infra-local"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    get_client("s3").head_bucket(Bucket=nomes["S3_BUCKET"])
