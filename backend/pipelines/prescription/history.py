"""Persistência e consulta do histórico de prescrições no DynamoDB.

Reaproveita o schema genérico `pk`/`sk` (String) já provisionado pela
aws-foundation — nenhuma tabela nova é criada por este módulo.
"""

import os

from botocore.exceptions import ClientError

from aws.clients import get_client
from pipelines.prescription.models import PrescriptionRecord


def _table_name() -> str:
    name = os.environ.get("DYNAMODB_TABLE")
    if not name:
        raise RuntimeError("DYNAMODB_TABLE não definida")
    return name


def _pk(patient_id: str, drug: str) -> str:
    return f"PATIENT#{patient_id}#DRUG#{drug}"


def dedup_key(bucket: str, key: str, etag: str) -> str:
    """Chave de deduplicação determinística a partir do evento S3."""
    return f"{bucket}/{key}#{etag}"


def save_record(record: PrescriptionRecord, dedup_key: str) -> bool:
    """Persiste o registro. Devolve ``False`` sem duplicar se ``dedup_key`` já existe."""
    client = get_client("dynamodb")
    item = {
        "pk": {"S": _pk(record.patient_id, record.drug)},
        "sk": {"S": record.timestamp},
        "patient_id": {"S": record.patient_id},
        "drug": {"S": record.drug},
        "dose": {"N": str(record.dose)},
        "unit": {"S": record.unit},
        "frequency": {"S": record.frequency},
        "dedup_key": {"S": dedup_key},
    }
    try:
        client.put_item(
            TableName=_table_name(),
            Item=item,
            ConditionExpression="attribute_not_exists(dedup_key)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True


def get_latest(patient_id: str, drug: str) -> PrescriptionRecord | None:
    """Devolve o registro mais recente do paciente/medicamento, ou ``None``."""
    client = get_client("dynamodb")
    response = client.query(
        TableName=_table_name(),
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": {"S": _pk(patient_id, drug)}},
        ScanIndexForward=False,
        Limit=1,
    )
    items = response.get("Items", [])
    if not items:
        return None

    item = items[0]
    return PrescriptionRecord(
        patient_id=item["patient_id"]["S"],
        drug=item["drug"]["S"],
        dose=float(item["dose"]["N"]),
        unit=item["unit"]["S"],
        frequency=item["frequency"]["S"],
        timestamp=item["sk"]["S"],
    )
