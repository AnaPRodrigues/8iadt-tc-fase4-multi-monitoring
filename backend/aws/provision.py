"""IaC idempotente dos recursos compartilhados (AD-034, AWSF-06).

Cada `ensure_*` checa existência antes de criar — nunca "cria e ignora erro de
já existir". Roda igual nos dois ambientes; só o endpoint muda (via `ENV`).
"""

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
