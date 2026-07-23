"""Testes de integração de `pipelines.fusion.handler` contra LocalStack real
(SNS + DynamoDB) -- FUSION-07, FUSION-08, FUSION-09.

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566. Uma fila SQS assinando o tópico SNS (raw message delivery)
comprova a publicação real -- sem isso não haveria como observar de fora se o
`publish` de fato aconteceu.

Também cobre `app.routes._is_confirmed` (FUSION-09, lado da leitura): o
handler grava o dedupe no DynamoDB real e a API real lê de volta -- os testes
de `test_routes.py` só cobrem `_is_confirmed` via monkeypatch ou a guarda
`DYNAMODB_TABLE` ausente, nunca a chamada real a `client.get_item(...)`.
"""

import socket
import uuid

import pytest

from app.routes import _is_confirmed
from aws.clients import get_client
from aws.provision import ensure_table, ensure_topic
from pipelines.fusion.handler import lambda_handler


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


@pytest.fixture
def table(monkeypatch):
    nome = f"mm-test-fusion-alert-{uuid.uuid4().hex[:8]}"
    ensure_table(nome)
    monkeypatch.setenv("DYNAMODB_TABLE", nome)
    return nome


@pytest.fixture
def topic_com_fila(monkeypatch):
    """Tópico SNS real + fila SQS assinante (raw delivery) para observar publicações."""
    topic_name = f"mm-test-fusion-topic-{uuid.uuid4().hex[:8]}"
    ensure_topic(topic_name)
    sns = get_client("sns")
    topic_arn = next(
        t["TopicArn"]
        for page in sns.get_paginator("list_topics").paginate()
        for t in page["Topics"]
        if t["TopicArn"].endswith(f":{topic_name}")
    )

    sqs = get_client("sqs")
    queue_name = f"mm-test-fusion-queue-{uuid.uuid4().hex[:8]}"
    queue_url = sqs.create_queue(QueueName=queue_name)["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]

    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
        Attributes={"RawMessageDelivery": "true"},
    )

    monkeypatch.setenv("SNS_TOPIC", topic_name)
    return {"topic_arn": topic_arn, "queue_url": queue_url}


def _mensagens_da_fila(queue_url: str) -> list[str]:
    """Corpo bruto das mensagens -- `RawMessageDelivery=true` faz a fila receber o
    texto publicado diretamente, sem o envelope JSON padrão do SNS."""
    sqs = get_client("sqs")
    response = sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2
    )
    return [m["Body"] for m in response.get("Messages", [])]


def _dynamo_tem_item(table_name: str, dedup_key: str) -> bool:
    client = get_client("dynamodb")
    response = client.get_item(
        TableName=table_name,
        Key={"pk": {"S": f"ALERT#{dedup_key}"}, "sk": {"S": "ALERT"}},
    )
    return "Item" in response


def _payload(dedup_key: str) -> dict:
    return {
        "patient_demo_id": "demo-1",
        "level": "vermelho",
        "dedup_key": dedup_key,
        "contributions": [["video", "queda detectada", "/evidence/fall-01"]],
    }


def test_handler_publica_no_sns_e_grava_dedupe_no_sucesso(table, topic_com_fila):
    dedup_key = f"fall-01-{uuid.uuid4().hex[:6]}"

    response = lambda_handler(_payload(dedup_key), context=None)

    assert response["published"] is True
    mensagens = _mensagens_da_fila(topic_com_fila["queue_url"])
    assert len(mensagens) == 1
    assert "demo-1" in mensagens[0]
    assert "vermelho" in mensagens[0]
    assert _dynamo_tem_item(table, dedup_key) is True


def test_handler_segunda_tentativa_com_mesmo_dedup_key_nao_duplica_email(table, topic_com_fila):
    dedup_key = f"fall-02-{uuid.uuid4().hex[:6]}"

    primeira = lambda_handler(_payload(dedup_key), context=None)
    segunda = lambda_handler(_payload(dedup_key), context=None)

    assert primeira.get("published") is True
    assert segunda.get("deduped") is True
    mensagens = _mensagens_da_fila(topic_com_fila["queue_url"])
    assert len(mensagens) == 1  # só a primeira tentativa publicou


def test_handler_falha_de_publish_nao_grava_dedupe_e_permite_nova_tentativa(
    table, topic_com_fila, monkeypatch
):
    import pipelines.fusion.handler as handler_module

    dedup_key = f"fall-03-{uuid.uuid4().hex[:6]}"
    publish_real = handler_module._publish

    def _publish_quebrado(payload):
        raise RuntimeError("SNS indisponível")

    monkeypatch.setattr(handler_module, "_publish", _publish_quebrado)

    resposta_com_falha = lambda_handler(_payload(dedup_key), context=None)

    assert resposta_com_falha["published"] is False
    assert _dynamo_tem_item(table, dedup_key) is False  # não gravou dedupe na falha

    monkeypatch.setattr(handler_module, "_publish", publish_real)  # restaura para a nova tentativa
    resposta_retry = lambda_handler(_payload(dedup_key), context=None)

    assert resposta_retry["published"] is True  # nova tentativa consegue publicar
    mensagens = _mensagens_da_fila(topic_com_fila["queue_url"])
    assert len(mensagens) == 1  # só o retry bem-sucedido publicou de fato


def test_is_confirmed_le_o_item_real_do_dynamodb_gravado_pelo_handler(table, topic_com_fila):
    dedup_key = f"fall-04-{uuid.uuid4().hex[:6]}"

    assert _is_confirmed(dedup_key) is False  # nenhum alerta gravado ainda

    lambda_handler(_payload(dedup_key), context=None)

    assert _is_confirmed(dedup_key) is True  # handler gravou ALERT#<dedup_key> de verdade
