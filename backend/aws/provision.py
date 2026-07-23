"""IaC idempotente dos recursos compartilhados.

Cada `ensure_*` checa existência antes de criar — nunca "cria e ignora erro de
já existir". Roda igual nos dois ambientes; só o endpoint muda (via `ENV`).
"""

import os
import sys
from dataclasses import dataclass

from botocore.exceptions import ClientError

from aws.clients import get_client
from common.logging import get_logger

log = get_logger("aws.provision")


@dataclass(frozen=True)
class ProvisionResult:
    resource: str
    created: bool  # True = criado agora; False = já existia


def ensure_bucket(name: str) -> ProvisionResult:
    client = get_client("s3")
    try:
        client.head_bucket(Bucket=name)
        log.info("bucket %s já existe", name)
        return ProvisionResult(resource=name, created=False)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in ("404", "NoSuchBucket"):
            raise
    client.create_bucket(Bucket=name)
    log.info("bucket %s criado", name)
    return ProvisionResult(resource=name, created=True)


def ensure_topic(name: str) -> ProvisionResult:
    client = get_client("sns")
    paginator = client.get_paginator("list_topics")
    for page in paginator.paginate():
        for topic in page.get("Topics", []):
            if topic["TopicArn"].endswith(f":{name}"):
                log.info("tópico %s já existe", name)
                return ProvisionResult(resource=name, created=False)
    client.create_topic(Name=name)
    log.info("tópico %s criado", name)
    return ProvisionResult(resource=name, created=True)


def ensure_table(name: str) -> ProvisionResult:
    client = get_client("dynamodb")
    try:
        client.describe_table(TableName=name)
        log.info("tabela %s já existe", name)
        return ProvisionResult(resource=name, created=False)
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    client.get_waiter("table_exists").wait(TableName=name)
    log.info("tabela %s criada", name)
    return ProvisionResult(resource=name, created=True)


def ensure_subscription(topic_arn: str, email: str) -> None:
    """Inscreve `email` no tópico SNS `topic_arn`, sem reenviar confirmação se já
    inscrito (pendente ou confirmada) — a confirmação de inscrição do SNS é um
    clique manual no e-mail, reenviar o convite a cada execução seria ruído."""
    client = get_client("sns")
    paginator = client.get_paginator("list_subscriptions_by_topic")
    for page in paginator.paginate(TopicArn=topic_arn):
        for sub in page.get("Subscriptions", []):
            if sub.get("Protocol") == "email" and sub.get("Endpoint") == email:
                log.info("e-mail %s já inscrito no tópico %s", email, topic_arn)
                return
    client.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    log.info("e-mail %s inscrito no tópico %s (confirmação manual pendente)", email, topic_arn)


def main() -> int:
    """Provisiona os três recursos compartilhados (`make infra-local`/`infra-cloud`)."""
    required = {
        "S3_BUCKET": os.environ.get("S3_BUCKET"),
        "SNS_TOPIC": os.environ.get("SNS_TOPIC"),
        "DYNAMODB_TABLE": os.environ.get("DYNAMODB_TABLE"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        log.error("variável(is) ausente(s): %s", ", ".join(missing))
        return 1

    try:
        results = [
            ensure_bucket(required["S3_BUCKET"]),
            ensure_topic(required["SNS_TOPIC"]),
            ensure_table(required["DYNAMODB_TABLE"]),
        ]
    except Exception as exc:  # conexão recusada (LocalStack fora do ar), etc.
        log.error(
            "provisionamento falhou: %s\n"
            "Se ENV=local, confirme que o LocalStack está de pé: make localstack-up",
            exc,
        )
        return 1

    for result in results:
        log.info("%s: %s", result.resource, "criado" if result.created else "já existia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
