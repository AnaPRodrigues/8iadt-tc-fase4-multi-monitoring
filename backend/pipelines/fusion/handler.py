"""Handler Lambda fino do alerta explicável de F5 -- publica no SNS o payload já
montado por `alert.py::build_payload` e grava o dedupe no DynamoDB (FUSION-07,
FUSION-08, FUSION-09).

Mesmo esqueleto fino de `pipelines/video/handler.py`/`pipelines/prescription/handler.py`
(try/except ao redor da chamada externa, log + segue sem propagar). Reserva o
`dedup_key` no DynamoDB ANTES de publicar (mesmo princípio de dedupe condicional de
`pipelines/prescription/history.py`, `ConditionExpression="attribute_not_exists(...)"`,
mesma tabela genérica com prefixo `ALERT#`) -- uma segunda tentativa com o mesmo
`dedup_key` é rejeitada pela reserva, sem duplicar e-mail (FUSION-08). Se a
publicação falhar depois da reserva, a reserva é desfeita, para que uma nova
tentativa seja possível depois (FUSION-09): o dedupe só permanece gravado quando o
envio de fato teve sucesso.
"""

import os
from typing import Any

from botocore.exceptions import ClientError

from aws.clients import get_client
from common.logging import get_logger

log = get_logger("fusion.handler")

_ALERT_SK = "ALERT"
_DEFAULT_SNS_TOPIC = "mm-alerts"


def _table_name() -> str:
    name = os.environ.get("DYNAMODB_TABLE")
    if not name:
        raise RuntimeError("DYNAMODB_TABLE não definida")
    return name


def _pk(dedup_key: str) -> str:
    return f"ALERT#{dedup_key}"


def _reserve_dedupe(dedup_key: str) -> bool:
    """Reserva `dedup_key` de forma atômica. Devolve `False` sem gravar nada se já
    reservado -- é essa rejeição condicional que evita o e-mail duplicado."""
    client = get_client("dynamodb")
    try:
        client.put_item(
            TableName=_table_name(),
            Item={"pk": {"S": _pk(dedup_key)}, "sk": {"S": _ALERT_SK}},
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def _release_dedupe(dedup_key: str) -> None:
    """Desfaz a reserva -- chamado só quando a publicação falha, para permitir
    nova tentativa depois (FUSION-09)."""
    client = get_client("dynamodb")
    client.delete_item(
        TableName=_table_name(), Key={"pk": {"S": _pk(dedup_key)}, "sk": {"S": _ALERT_SK}}
    )


def _topic_arn(name: str) -> str:
    client = get_client("sns")
    for page in client.get_paginator("list_topics").paginate():
        for topic in page.get("Topics", []):
            if topic["TopicArn"].endswith(f":{name}"):
                return topic["TopicArn"]
    raise RuntimeError(f"tópico SNS inexistente: {name}")


def _message(payload: dict[str, Any]) -> str:
    linhas = [
        f"Paciente-demo: {payload['patient_demo_id']}",
        f"Nível: {payload['level']}",
        "",
        "Sinais contribuintes:",
    ]
    for modality, summary, link in payload["contributions"]:
        linhas.append(f"- [{modality}] {summary} -- {link}")
    return "\n".join(linhas)


def _publish(payload: dict[str, Any]) -> None:
    topic_name = os.environ.get("SNS_TOPIC", _DEFAULT_SNS_TOPIC)
    client = get_client("sns")
    subject = f"Alerta {payload['level']} -- paciente-demo {payload['patient_demo_id']}"
    client.publish(
        TopicArn=_topic_arn(topic_name),
        Subject=subject[:100],  # limite do SNS
        Message=_message(payload),
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict:
    """Handler Lambda: `event` é o payload explicável já montado por
    `alert.py::build_payload` (serializado), com `patient_demo_id`, `level`,
    `dedup_key`, `contributions`."""
    dedup_key = event["dedup_key"]

    if not _reserve_dedupe(dedup_key):
        log.info("alerta já enviado para dedup_key=%s -- ignorando (dedupe)", dedup_key)
        return {"statusCode": 200, "deduped": True}

    try:
        _publish(event)
    except Exception:
        log.exception(
            "falha ao publicar alerta no SNS -- não propaga; nova tentativa possível depois"
        )
        _release_dedupe(dedup_key)
        return {"statusCode": 200, "published": False}

    return {"statusCode": 200, "published": True}
