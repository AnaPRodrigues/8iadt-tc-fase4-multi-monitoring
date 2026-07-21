"""Handler Lambda fino: lê o evento S3, baixa o objeto, chama `logic.process`.

Erro de extração/parsing é logado e o objeto movido para `errors/` no S3 — nunca
propaga exceção que travaria o processamento do lote (PRESC-07).
"""

from typing import Any

from aws.clients import get_client
from common.logging import get_logger
from pipelines.prescription.logic import process

log = get_logger("prescription.handler")

_ERROR_PREFIX = "errors/"


def _move_to_errors(client: Any, bucket: str, key: str) -> None:
    client.copy_object(
        Bucket=bucket, CopySource={"Bucket": bucket, "Key": key}, Key=f"{_ERROR_PREFIX}{key}"
    )
    client.delete_object(Bucket=bucket, Key=key)


def _handle_record(record: dict) -> None:
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]
    etag = record["s3"]["object"]["eTag"]
    client = get_client("s3")

    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        pdf_bytes = obj["Body"].read()
        result = process(pdf_bytes, bucket, key, etag)
    except Exception:
        log.exception("erro processando %s/%s -- movendo para %s", bucket, key, _ERROR_PREFIX)
        _move_to_errors(client, bucket, key)
        return

    if result.parse_failure is not None:
        log.warning("parsing incompleto em %s/%s: %s", bucket, key, result.parse_failure.reason)
        _move_to_errors(client, bucket, key)
        return

    log.info(
        "processado %s/%s: anomalias=%s dedup=%s",
        bucket,
        key,
        [a.kind for a in result.anomalies],
        result.deduplicated,
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict:
    """Handler Lambda: processa cada registro do evento S3 (`Records`)."""
    for record in event.get("Records", []):
        _handle_record(record)
    return {"statusCode": 200}
