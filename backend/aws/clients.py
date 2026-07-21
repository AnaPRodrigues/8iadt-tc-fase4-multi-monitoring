"""Factory único de cliente boto3, selecionado por `ENV` (AD-034).

Nenhum outro módulo em `backend/` deve chamar `boto3.client(...)` diretamente
— um teste de guarda (`test_no_direct_boto3_client.py`) torna isso executável.
"""

import os
from dataclasses import dataclass

from common.logging import get_logger

log = get_logger("aws.clients")

_VALID_ENVS = ("local", "cloud")


@dataclass(frozen=True)
class AwsConfig:
    env: str
    region: str
    endpoint_url: str | None


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"variável de ambiente obrigatória ausente: {name}")
    return value


def load_aws_config() -> AwsConfig:
    """Lê e valida a config do ambiente ativo. Não faz nenhuma chamada AWS."""
    env = _require("ENV")
    if env not in _VALID_ENVS:
        raise ValueError(f"ENV inválido: {env!r} (esperado 'local' ou 'cloud')")

    region = _require("AWS_REGION")

    endpoint_url = None
    if env == "local":
        endpoint_url = _require("LOCALSTACK_ENDPOINT")

    return AwsConfig(env=env, region=region, endpoint_url=endpoint_url)
