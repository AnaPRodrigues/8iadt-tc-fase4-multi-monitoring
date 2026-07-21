"""Provisiona os recursos específicos de F4 que a fundação não cobre: a função
Lambda e o gatilho S3→Lambda (PRESC-02, PRESC-07, PRESC-08).

S3/DynamoDB genéricos já vêm de `aws.provision`; este módulo só acrescenta a
Lambda e a notificação do bucket, reaproveitando o padrão idempotente
"checar antes de criar".
"""

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from aws.clients import get_client
from aws.provision import ProvisionResult
from common.logging import get_logger

log = get_logger("prescription.infra")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HANDLER = "pipelines.prescription.handler.lambda_handler"
_DEFAULT_LAMBDA_NAME = "mm-prescription-processor"
_DEFAULT_LOCAL_ROLE_ARN = "arn:aws:iam::000000000000:role/lambda-role"


def _install_dependencies(target: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--target",
            str(target),
            "pdfplumber>=0.11",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"falha ao instalar dependências do Lambda: {result.stderr}")


def _copy_source(target: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_REPO_ROOT / "backend" / "aws", target / "aws", ignore=ignore)
    shutil.copytree(_REPO_ROOT / "backend" / "common", target / "common", ignore=ignore)
    (target / "pipelines").mkdir()
    (target / "pipelines" / "__init__.py").write_text("")
    shutil.copytree(
        _REPO_ROOT / "backend" / "pipelines" / "prescription",
        target / "pipelines" / "prescription",
        ignore=ignore,
    )


def _zip_dir(source: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source))
    return buffer.getvalue()


def package_lambda() -> bytes:
    """Empacota `handler.py` + módulos de `pipelines/prescription/` + dependências."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        _install_dependencies(target)
        _copy_source(target)
        return _zip_dir(target)


def role_arn() -> str:
    """`LAB_ROLE_ARN` no cloud (AD-007); ARN dummy aceito pelo LocalStack no local."""
    return os.environ.get("LAB_ROLE_ARN") or _DEFAULT_LOCAL_ROLE_ARN


def function_arn(name: str) -> str:
    return get_client("lambda").get_function(FunctionName=name)["Configuration"]["FunctionArn"]


def _env_vars() -> dict[str, str]:
    """Variáveis que o handler precisa em runtime dentro do próprio Lambda.

    SPEC_DEVIATION: o design não previa este parâmetro — descoberto empiricamente
    que o container Lambda do LocalStack não herda o shell do host; sem isso,
    `aws.clients.load_aws_config()`/`history._table_name()` falham em runtime
    (ver fix em `aws/clients.py`, fallback de `LOCALSTACK_HOSTNAME`).
    """
    # LOCALSTACK_ENDPOINT do host (ex.: http://localhost:4566) NUNCA é propagada:
    # de dentro do container ela seria o loopback do próprio Lambda, não o
    # LocalStack — o fallback de LOCALSTACK_HOSTNAME/EDGE_PORT em aws.clients
    # resolve isso automaticamente em runtime.
    env_vars = {"ENV": os.environ.get("ENV", "local")}
    if region := os.environ.get("AWS_REGION"):
        env_vars["AWS_REGION"] = region
    if table := os.environ.get("DYNAMODB_TABLE"):
        env_vars["DYNAMODB_TABLE"] = table
    return env_vars


def ensure_lambda(name: str, zip_bytes: bytes, role: str) -> ProvisionResult:
    """Cria a função Lambda, ou atualiza código+config se já existir (checar-antes-de-criar)."""
    client = get_client("lambda")
    env_vars = _env_vars()
    try:
        client.get_function(FunctionName=name)
        client.update_function_code(FunctionName=name, ZipFile=zip_bytes)
        client.get_waiter("function_updated_v2").wait(FunctionName=name)
        client.update_function_configuration(FunctionName=name, Environment={"Variables": env_vars})
        client.get_waiter("function_updated_v2").wait(FunctionName=name)
        log.info("função %s já existia; código e config atualizados", name)
        return ProvisionResult(resource=name, created=False)
    except client.exceptions.ResourceNotFoundException:
        pass

    client.create_function(
        FunctionName=name,
        Runtime="python3.12",
        Role=role,
        Handler=_HANDLER,
        Code={"ZipFile": zip_bytes},
        Timeout=30,
        MemorySize=512,
        Environment={"Variables": env_vars},
    )
    client.get_waiter("function_active_v2").wait(FunctionName=name)
    log.info("função %s criada", name)
    return ProvisionResult(resource=name, created=True)


def ensure_s3_trigger(bucket: str, lambda_function_arn: str) -> ProvisionResult:
    """Configura a notificação do bucket + a permissão do Lambda para o S3 invocar."""
    lambda_client = get_client("lambda")
    s3_client = get_client("s3")

    with contextlib.suppress(lambda_client.exceptions.ResourceConflictException):
        lambda_client.add_permission(
            FunctionName=lambda_function_arn,
            StatementId=f"s3invoke-{bucket}",
            Action="lambda:InvokeFunction",
            Principal="s3.amazonaws.com",
            SourceArn=f"arn:aws:s3:::{bucket}",
        )  # permissão já concedida — idempotente

    existing = s3_client.get_bucket_notification_configuration(Bucket=bucket)
    already_configured = any(
        cfg.get("LambdaFunctionArn") == lambda_function_arn
        for cfg in existing.get("LambdaFunctionConfigurations", [])
    )
    if already_configured:
        log.info("gatilho S3→Lambda de %s já configurado", bucket)
        return ProvisionResult(resource=bucket, created=False)

    s3_client.put_bucket_notification_configuration(
        Bucket=bucket,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {"LambdaFunctionArn": lambda_function_arn, "Events": ["s3:ObjectCreated:*"]}
            ]
        },
    )
    log.info("gatilho S3→Lambda configurado em %s", bucket)
    return ProvisionResult(resource=bucket, created=True)


def main() -> int:
    """Provisiona a Lambda de F4 e o gatilho S3 (`make infra-local`/`infra-cloud`)."""
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        log.error("variável ausente: S3_BUCKET")
        return 1

    lambda_name = os.environ.get("PRESCRIPTION_LAMBDA_NAME", _DEFAULT_LAMBDA_NAME)
    try:
        zip_bytes = package_lambda()
        ensure_lambda(lambda_name, zip_bytes, role_arn())
        arn = function_arn(lambda_name)
        ensure_s3_trigger(bucket, arn)
    except Exception as exc:
        log.error(
            "provisionamento da lambda de prescrição falhou: %s\n"
            "Se ENV=local, confirme que o LocalStack está de pé: make localstack-up",
            exc,
        )
        return 1

    log.info("lambda %s provisionada; gatilho S3 configurado em %s", lambda_name, bucket)
    return 0


if __name__ == "__main__":
    sys.exit(main())
