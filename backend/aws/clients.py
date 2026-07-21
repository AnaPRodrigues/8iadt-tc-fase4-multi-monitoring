"""Factory único de cliente boto3, selecionado por `ENV` (AD-034).

Nenhum outro módulo em `backend/` deve chamar `boto3.client(...)` diretamente
— um teste de guarda (`test_no_direct_boto3_client.py`) torna isso executável.
"""

import os
from dataclasses import dataclass
from typing import Any

import boto3

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


def _local_endpoint() -> str:
    """``LOCALSTACK_ENDPOINT`` explícita ou, dentro de um container Lambda do
    próprio LocalStack, construída a partir de ``LOCALSTACK_HOSTNAME``/``EDGE_PORT``
    (injetadas automaticamente pelo LocalStack no runtime do Lambda — confirmado
    empiricamente durante a implementação de F4/infra.py: o container não recebe
    nossa variável de projeto, só as suas próprias).
    """
    explicit = os.environ.get("LOCALSTACK_ENDPOINT")
    if explicit:
        return explicit

    hostname = os.environ.get("LOCALSTACK_HOSTNAME")
    if not hostname:
        raise ValueError("variável de ambiente obrigatória ausente: LOCALSTACK_ENDPOINT")
    port = os.environ.get("EDGE_PORT", "4566")
    return f"http://{hostname}:{port}"


def load_aws_config() -> AwsConfig:
    """Lê e valida a config do ambiente ativo. Não faz nenhuma chamada AWS."""
    env = _require("ENV")
    if env not in _VALID_ENVS:
        raise ValueError(f"ENV inválido: {env!r} (esperado 'local' ou 'cloud')")

    region = _require("AWS_REGION")

    endpoint_url = None
    if env == "local":
        endpoint_url = _local_endpoint()

    return AwsConfig(env=env, region=region, endpoint_url=endpoint_url)


def get_client(service: str, config: AwsConfig | None = None) -> Any:
    """Único ponto de criação de clientes boto3 do projeto (AD-034).

    `ENV=local` injeta o endpoint do LocalStack e credenciais dummy; `ENV=cloud`
    usa a cadeia de credenciais padrão da sessão (perfil/env do Learner Lab), sem
    `endpoint_url`. Se o LocalStack não estiver de pé, a chamada de rede que o
    cliente eventualmente fizer falha com o erro de conexão do próprio boto3 —
    rode `make localstack-up` antes de usar `ENV=local`.
    """
    cfg = config or load_aws_config()
    if cfg.env == "local":
        log.info("cliente %s via LocalStack (%s)", service, cfg.endpoint_url)
        return boto3.client(
            service,
            endpoint_url=cfg.endpoint_url,
            region_name=cfg.region,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
    log.info("cliente %s via AWS (%s)", service, cfg.region)
    return boto3.client(service, region_name=cfg.region)
