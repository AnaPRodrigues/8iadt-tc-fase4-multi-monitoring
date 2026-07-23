"""Testes de integração de `infra.py` contra LocalStack real — deploy verdadeiro
do Lambda, disparado por um evento S3 real (não simulado).

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566. Compartilha um único deploy entre os testes do módulo
(package+deploy tem custo; recriar por teste seria caro sem ganho).

Rekognition não existe no LocalStack Community -- o `analyze()` real
dentro do Lambda implantado necessariamente falha (ou por falta de adapter
registrado, ou pela chamada Rekognition em si), e `handler.py` já trata isso
sem propagar. O que este módulo prova é a fiação da infraestrutura --
o upload real no S3 dispara o Lambda de verdade -- via CloudWatch Logs, não
via evidência de análise (que não é alcançável neste ambiente).
"""

import os
import socket
import time
import uuid

import pytest

from aws.clients import get_client
from aws.provision import ensure_bucket
from pipelines.video import infra


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
    updates = {
        "ENV": "local",
        "AWS_REGION": "us-east-1",
        "LOCALSTACK_ENDPOINT": "http://localhost:4566",
    }
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
    bucket = f"mm-test-video-infra-bucket-{uuid.uuid4().hex[:8]}"
    lambda_name = f"mm-test-video-infra-lambda-{uuid.uuid4().hex[:8]}"

    ensure_bucket(bucket)

    zip_bytes = infra.package_lambda()
    infra.ensure_lambda(lambda_name, zip_bytes, infra.role_arn())
    arn = infra.function_arn(lambda_name)
    infra.ensure_s3_trigger(bucket, arn)

    yield {"bucket": bucket, "lambda_name": lambda_name, "arn": arn, "zip_bytes": zip_bytes}

    get_client("lambda").delete_function(FunctionName=lambda_name)


def _log_group_has_invocation(lambda_name: str) -> bool:
    logs = get_client("logs")
    log_group = f"/aws/lambda/{lambda_name}"
    try:
        streams = logs.describe_log_streams(logGroupName=log_group)["logStreams"]
    except logs.exceptions.ResourceNotFoundException:
        return False
    for stream in streams:
        events = logs.get_log_events(
            logGroupName=log_group, logStreamName=stream["logStreamName"]
        )["events"]
        if events:
            return True
    return False


def test_upload_real_dispara_lambda_de_verdade(deployed):
    s3 = get_client("s3")
    s3.put_object(
        Bucket=deployed["bucket"], Key="keyframes/upload.jpg", Body=b"conteudo-fake-de-teste"
    )

    for _ in range(20):
        if _log_group_has_invocation(deployed["lambda_name"]):
            break
        time.sleep(1)
    else:
        pytest.fail("Lambda não foi invocado a tempo pelo gatilho S3")


def test_ensure_lambda_segunda_chamada_nao_recria(deployed):
    result = infra.ensure_lambda(deployed["lambda_name"], deployed["zip_bytes"], infra.role_arn())
    assert result.created is False


def test_ensure_s3_trigger_segunda_chamada_nao_recria(deployed):
    result = infra.ensure_s3_trigger(deployed["bucket"], deployed["arn"])
    assert result.created is False


def test_package_lambda_produz_zip_valido():
    zip_bytes = infra.package_lambda()
    assert zip_bytes[:2] == b"PK"
