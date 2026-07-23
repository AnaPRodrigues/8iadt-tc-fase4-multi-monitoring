"""Provisiona os recursos específicos do alerta de F5 que a fundação não cobre: o
tópico SNS + assinaturas de e-mail, a tabela DynamoDB de dedupe (mesma tabela
genérica reusada com prefixo `ALERT#`, ver `handler.py`) e a função Lambda do
handler de alerta.

Mesmo padrão idempotente já validado em `pipelines/video/infra.py`/
`pipelines/prescription/infra.py` ("checar antes de criar"). Diferente dessas
duas, o handler de alerta não é disparado por um evento S3 -- é invocado
diretamente por quem decide que o nível de risco cruzou o limiar de disparo --
então não há bucket nem gatilho S3→Lambda a provisionar aqui, só o tópico, a
tabela, as inscrições e a função em si.

`handler.py` só depende de `boto3` (já embutido no runtime do Lambda) além dos
módulos próprios do projeto, então, como em `video/infra.py`, não há dependência
externa para instalar no zip; e só `handler.py` (não o resto de
`pipelines/fusion/`, que arrasta numpy/pyyaml) precisa ir no pacote.

A confirmação da inscrição de e-mail no SNS é um passo manual (clique no e-mail
de confirmação que a AWS/LocalStack envia) -- não é automatizável via boto3;
`ensure_subscription` (`aws/provision.py`) já é idempotente quanto a isso, não
reenvia convite se o e-mail já está inscrito.
"""

import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from aws.clients import get_client
from aws.provision import ProvisionResult, ensure_subscription, ensure_table, ensure_topic
from common.logging import get_logger

log = get_logger("fusion.infra")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HANDLER = "pipelines.fusion.handler.lambda_handler"
_DEFAULT_LAMBDA_NAME = "mm-fusion-alert"
_DEFAULT_LOCAL_ROLE_ARN = "arn:aws:iam::000000000000:role/lambda-role"


def _copy_source(target: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_REPO_ROOT / "backend" / "aws", target / "aws", ignore=ignore)
    shutil.copytree(_REPO_ROOT / "backend" / "common", target / "common", ignore=ignore)
    (target / "pipelines").mkdir()
    (target / "pipelines" / "__init__.py").write_text("")
    fusion_dir = target / "pipelines" / "fusion"
    fusion_dir.mkdir()
    (fusion_dir / "__init__.py").write_text("")
    shutil.copy2(
        _REPO_ROOT / "backend" / "pipelines" / "fusion" / "handler.py", fusion_dir / "handler.py"
    )


def _zip_dir(source: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(source))
    return buffer.getvalue()


def package_lambda() -> bytes:
    """Empacota `handler.py` (fino, só `boto3`) + `aws/`/`common/`."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        _copy_source(target)
        return _zip_dir(target)


def role_arn() -> str:
    """`LAB_ROLE_ARN` no cloud; ARN dummy aceito pelo LocalStack no local."""
    return os.environ.get("LAB_ROLE_ARN") or _DEFAULT_LOCAL_ROLE_ARN


def function_arn(name: str) -> str:
    return get_client("lambda").get_function(FunctionName=name)["Configuration"]["FunctionArn"]


def _topic_arn(name: str) -> str:
    client = get_client("sns")
    for page in client.get_paginator("list_topics").paginate():
        for topic in page.get("Topics", []):
            if topic["TopicArn"].endswith(f":{name}"):
                return topic["TopicArn"]
    raise RuntimeError(f"tópico SNS inexistente: {name}")


def _env_vars(table_name: str, topic_name: str) -> dict[str, str]:
    """Mesmo fallback de `LOCALSTACK_HOSTNAME` já usado em `prescription/infra.py`
    -- o container Lambda do LocalStack não herda o shell do host."""
    env_vars = {
        "ENV": os.environ.get("ENV", "local"),
        "DYNAMODB_TABLE": table_name,
        "SNS_TOPIC": topic_name,
    }
    if region := os.environ.get("AWS_REGION"):
        env_vars["AWS_REGION"] = region
    return env_vars


def ensure_lambda(
    name: str, zip_bytes: bytes, role: str, env_vars: dict[str, str]
) -> ProvisionResult:
    """Cria a função Lambda, ou atualiza código+config se já existir (checar-antes-de-criar)."""
    client = get_client("lambda")
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


def provision(
    *,
    topic_name: str,
    table_name: str,
    emails: list[str],
    lambda_name: str = _DEFAULT_LAMBDA_NAME,
) -> str:
    """Provisiona (idempotente) tudo que o handler de alerta precisa: tópico +
    tabela (reuso da fundação), inscrições de e-mail e a função Lambda em si.

    Devolve o ARN da função. Chamar duas vezes seguidas com os mesmos
    argumentos não falha nem duplica nada (idempotência).
    """
    ensure_topic(topic_name)
    ensure_table(table_name)
    topic_arn = _topic_arn(topic_name)

    for email in emails:
        ensure_subscription(topic_arn, email)

    zip_bytes = package_lambda()
    env_vars = _env_vars(table_name, topic_name)
    ensure_lambda(lambda_name, zip_bytes, role_arn(), env_vars)
    return function_arn(lambda_name)


def main() -> int:
    """Provisiona a infraestrutura de alerta de F5 (`SNS_TOPIC`, `DYNAMODB_TABLE`
    já usadas pela fundação; `ALERT_EMAILS` -- lista separada por vírgula dos
    e-mails da equipe do grupo -- lida do ambiente)."""
    topic_name = os.environ.get("SNS_TOPIC")
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not topic_name or not table_name:
        log.error("variável(is) ausente(s): SNS_TOPIC e/ou DYNAMODB_TABLE")
        return 1

    emails = [e.strip() for e in os.environ.get("ALERT_EMAILS", "").split(",") if e.strip()]
    lambda_name = os.environ.get("FUSION_LAMBDA_NAME", _DEFAULT_LAMBDA_NAME)

    try:
        arn = provision(
            topic_name=topic_name, table_name=table_name, emails=emails, lambda_name=lambda_name
        )
    except Exception as exc:
        log.error(
            "provisionamento da infraestrutura de alerta falhou: %s\n"
            "Se ENV=local, confirme que o LocalStack está de pé: make localstack-up",
            exc,
        )
        return 1

    log.info(
        "lambda %s provisionada (%s); %d e-mail(s) inscrito(s) -- confirmação por clique "
        "no e-mail continua manual, não automatizável via boto3",
        lambda_name,
        arn,
        len(emails),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
