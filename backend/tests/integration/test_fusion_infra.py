"""Testes de integração de `pipelines.fusion.infra` contra LocalStack real --
deploy verdadeiro do Lambda de alerta, tópico/tabela/inscrições reais.

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566. Mesmo padrão de `backend/tests/integration/test_video_infra.py`.
"""

import json
import socket
import uuid

import pytest

from aws.clients import get_client
from pipelines.fusion import infra


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


def _subscription_emails(topic_arn: str) -> list[str]:
    client = get_client("sns")
    subs = []
    for page in client.get_paginator("list_subscriptions_by_topic").paginate(TopicArn=topic_arn):
        subs.extend(page.get("Subscriptions", []))
    return [s["Endpoint"] for s in subs if s["Protocol"] == "email"]


@pytest.fixture
def recursos():
    return {
        "topic_name": f"mm-test-fusion-infra-topic-{uuid.uuid4().hex[:8]}",
        "table_name": f"mm-test-fusion-infra-table-{uuid.uuid4().hex[:8]}",
        "lambda_name": f"mm-test-fusion-infra-lambda-{uuid.uuid4().hex[:8]}",
        "email": "equipe@example.com",
    }


def test_provision_e_idempotente_rodando_duas_vezes(recursos):
    primeiro_arn = infra.provision(
        topic_name=recursos["topic_name"],
        table_name=recursos["table_name"],
        emails=[recursos["email"]],
        lambda_name=recursos["lambda_name"],
    )
    segundo_arn = infra.provision(
        topic_name=recursos["topic_name"],
        table_name=recursos["table_name"],
        emails=[recursos["email"]],
        lambda_name=recursos["lambda_name"],
    )

    assert primeiro_arn == segundo_arn
    get_client("lambda").get_function(FunctionName=recursos["lambda_name"])  # não lança


def test_provision_inscreve_os_emails_configurados(recursos):
    infra.provision(
        topic_name=recursos["topic_name"],
        table_name=recursos["table_name"],
        emails=[recursos["email"]],
        lambda_name=recursos["lambda_name"],
    )

    topic_arn = infra._topic_arn(recursos["topic_name"])
    assert recursos["email"] in _subscription_emails(topic_arn)


def test_provision_devolve_arn_real_da_funcao_lambda(recursos):
    arn = infra.provision(
        topic_name=recursos["topic_name"],
        table_name=recursos["table_name"],
        emails=[recursos["email"]],
        lambda_name=recursos["lambda_name"],
    )

    real = get_client("lambda").get_function(FunctionName=recursos["lambda_name"])
    assert arn == real["Configuration"]["FunctionArn"]


def test_lambda_provisionada_publica_de_verdade_quando_invocada(recursos):
    infra.provision(
        topic_name=recursos["topic_name"],
        table_name=recursos["table_name"],
        emails=[recursos["email"]],
        lambda_name=recursos["lambda_name"],
    )

    # Fila SQS assinando o mesmo tópico para observar a publicação real feita
    # de dentro da função Lambda implantada (prova de que os env vars
    # DYNAMODB_TABLE/SNS_TOPIC foram propagados corretamente para o runtime).
    sqs = get_client("sqs")
    queue_url = sqs.create_queue(QueueName=f"mm-test-fusion-infra-queue-{uuid.uuid4().hex[:8]}")[
        "QueueUrl"
    ]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    topic_arn = infra._topic_arn(recursos["topic_name"])
    get_client("sns").subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
        Attributes={"RawMessageDelivery": "true"},
    )

    payload = {
        "patient_demo_id": "demo-1",
        "level": "vermelho",
        "dedup_key": f"fall-{uuid.uuid4().hex[:6]}",
        "contributions": [["video", "queda detectada", "/evidence/fall-01"]],
    }
    response = get_client("lambda").invoke(
        FunctionName=recursos["lambda_name"],
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    corpo = json.loads(response["Payload"].read())

    assert corpo.get("published") is True
    mensagens = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=3)
    assert len(mensagens.get("Messages", [])) == 1


def test_package_lambda_produz_zip_valido():
    zip_bytes = infra.package_lambda()
    assert zip_bytes[:2] == b"PK"
