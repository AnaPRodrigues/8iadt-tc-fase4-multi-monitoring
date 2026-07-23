"""Testes de integração de `ensure_subscription` (`provision.py`) contra LocalStack real.

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566 -- mesmo padrão de `backend/tests/integration/test_aws_provision.py`.
"""

import socket
import uuid

import pytest

from aws.clients import get_client
from aws.provision import ensure_subscription, ensure_topic


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
def topic_arn():
    nome = f"mm-test-topic-{uuid.uuid4().hex[:8]}"
    ensure_topic(nome)
    client = get_client("sns")
    for page in client.get_paginator("list_topics").paginate():
        for topic in page["Topics"]:
            if topic["TopicArn"].endswith(f":{nome}"):
                return topic["TopicArn"]
    raise RuntimeError("tópico recém-criado não encontrado")


def _subscription_emails(topic_arn: str) -> list[str]:
    client = get_client("sns")
    subs = []
    for page in client.get_paginator("list_subscriptions_by_topic").paginate(TopicArn=topic_arn):
        subs.extend(page.get("Subscriptions", []))
    return [s["Endpoint"] for s in subs if s["Protocol"] == "email"]


def test_ensure_subscription_inscreve_email_no_topico(topic_arn):
    email = "equipe@example.com"

    ensure_subscription(topic_arn, email)

    assert email in _subscription_emails(topic_arn)


def test_ensure_subscription_segunda_chamada_nao_duplica(topic_arn):
    email = "equipe@example.com"

    ensure_subscription(topic_arn, email)
    ensure_subscription(topic_arn, email)

    assert _subscription_emails(topic_arn).count(email) == 1
