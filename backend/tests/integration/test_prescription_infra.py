"""Testes de integração de infra.py contra LocalStack real — deploy verdadeiro
do Lambda, disparado por um evento S3 real (não simulado).

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566. Compartilha um único deploy entre os testes do módulo
(package+deploy leva ~15-20s; recriar por teste seria caro sem ganho).
"""

import os
import socket
import time
import uuid

import pytest

from aws.clients import get_client
from aws.provision import ensure_bucket, ensure_table
from pipelines.prescription import infra
from pipelines.prescription.generator import generate_prescription


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


@pytest.fixture(scope="module")
def env_local():
    updates = {"ENV": "local", "AWS_REGION": "us-east-1", "LOCALSTACK_ENDPOINT": "http://localhost:4566"}
    previous = {k: os.environ.get(k) for k in updates}
    os.environ.update(updates)
    yield
    for k, v in previous.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(scope="module")
def deployed(env_local):
    table = f"mm-test-infra-table-{uuid.uuid4().hex[:8]}"
    bucket = f"mm-test-infra-bucket-{uuid.uuid4().hex[:8]}"
    lambda_name = f"mm-test-infra-lambda-{uuid.uuid4().hex[:8]}"
    os.environ["DYNAMODB_TABLE"] = table

    ensure_bucket(bucket)
    ensure_table(table)

    zip_bytes = infra.package_lambda()
    infra.ensure_lambda(lambda_name, zip_bytes, infra.role_arn())
    arn = infra.function_arn(lambda_name)
    infra.ensure_s3_trigger(bucket, arn)

    yield {
        "table": table,
        "bucket": bucket,
        "lambda_name": lambda_name,
        "arn": arn,
        "zip_bytes": zip_bytes,
    }

    get_client("lambda").delete_function(FunctionName=lambda_name)
    os.environ.pop("DYNAMODB_TABLE", None)


def test_upload_real_dispara_lambda_e_grava_no_dynamodb(deployed):
    pdf_bytes = generate_prescription(
        patient_id="infra-p1", drug="paracetamol", dose=500, frequency="8/8h", seed=1
    )
    s3 = get_client("s3")
    s3.put_object(Bucket=deployed["bucket"], Key="prescricoes/p1.pdf", Body=pdf_bytes)

    ddb = get_client("dynamodb")
    items: list = []
    for _ in range(20):
        resp = ddb.query(
            TableName=deployed["table"],
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": {"S": "PATIENT#infra-p1#DRUG#paracetamol"}},
        )
        items = resp.get("Items", [])
        if items:
            break
        time.sleep(1)
    else:
        pytest.fail("Lambda não processou o evento S3 a tempo")

    assert items[0]["dose"]["N"] == "500"


def test_ensure_lambda_segunda_chamada_nao_recria(deployed):
    result = infra.ensure_lambda(deployed["lambda_name"], deployed["zip_bytes"], infra.role_arn())
    assert result.created is False


def test_ensure_s3_trigger_segunda_chamada_nao_recria(deployed):
    result = infra.ensure_s3_trigger(deployed["bucket"], deployed["arn"])
    assert result.created is False


def test_package_lambda_produz_zip_valido():
    zip_bytes = infra.package_lambda()
    assert zip_bytes[:2] == b"PK"
