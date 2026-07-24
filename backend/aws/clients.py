"""Factory de cliente da AWS, usado apenas no modo `ENV=aws`.

O sistema tem dois modos, escolhidos pela variável de ambiente `ENV`:

- `local` (padrão): todo o processamento é local, sem nenhuma chamada de nuvem.
  Este factory **não** é usado nesse modo.
- `aws`: usa exatamente dois serviços gerenciados — Amazon Textract (extração de
  texto/campos de documentos) e Amazon Rekognition (rótulos de objetos em imagens).

Só esses dois serviços são permitidos aqui; qualquer outro é recusado. Nenhum
outro módulo cria um cliente da AWS diretamente (há um teste de guarda que garante
isso).
"""

import os
from dataclasses import dataclass
from typing import Any

import boto3

from common.logging import get_logger

log = get_logger("aws.clients")

_VALID_ENVS = ("local", "aws")
_ALLOWED_SERVICES = ("textract", "rekognition")


@dataclass(frozen=True)
class AwsConfig:
    env: str
    region: str


def resolve_env() -> str:
    """Modo ativo. Ausente ou vazio equivale ao padrão `local`."""
    env = os.environ.get("ENV") or "local"
    if env not in _VALID_ENVS:
        raise ValueError(f"ENV inválido: {env!r} (esperado 'local' ou 'aws')")
    return env


def load_aws_config() -> AwsConfig:
    """Lê e valida a configuração do modo `aws`. Não faz nenhuma chamada de rede.

    Só faz sentido no modo `aws` — a região é obrigatória ali. Chamar no modo
    `local` é um erro de uso: no modo local não há acesso a serviços de nuvem.
    """
    env = resolve_env()
    if env != "aws":
        raise ValueError(
            "load_aws_config só se aplica ao modo aws; "
            f"ENV atual é {env!r} (nenhum serviço de nuvem é usado no modo local)"
        )

    region = os.environ.get("AWS_REGION")
    if not region:
        raise ValueError("variável de ambiente obrigatória ausente: AWS_REGION")

    return AwsConfig(env=env, region=region)


def get_client(service: str, config: AwsConfig | None = None) -> Any:
    """Cria um cliente da AWS para `service` (só `textract` ou `rekognition`).

    Usa a cadeia de credenciais padrão da sessão (perfil/variáveis já configurados
    no ambiente). Só deve ser chamado no modo `aws`.
    """
    if service not in _ALLOWED_SERVICES:
        raise ValueError(
            f"serviço de nuvem não permitido: {service!r} "
            f"(apenas {', '.join(_ALLOWED_SERVICES)} são usados)"
        )
    cfg = config or load_aws_config()
    log.info("cliente %s da AWS (região %s)", service, cfg.region)
    return boto3.client(service, region_name=cfg.region)
