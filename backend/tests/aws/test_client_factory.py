"""Testes do factory de cliente da AWS (usado só no modo `aws`).

Sem Docker e sem credencial real: só resolução de configuração e as guardas de
uso. A criação do cliente boto3 em si é coberta pelo teste do caminho de nuvem
com dublê (`test_cloud_adapters.py`).
"""

import pytest

from aws.clients import get_client, load_aws_config, resolve_env


def test_env_ausente_equivale_ao_modo_local_padrao(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)

    assert resolve_env() == "local"


def test_env_vazio_equivale_ao_modo_local_padrao(monkeypatch):
    monkeypatch.setenv("ENV", "")

    assert resolve_env() == "local"


def test_env_aws_e_reconhecido(monkeypatch):
    monkeypatch.setenv("ENV", "aws")

    assert resolve_env() == "aws"


def test_env_invalido_nomeia_o_valor_recebido(monkeypatch):
    monkeypatch.setenv("ENV", "xpto")

    with pytest.raises(ValueError, match="xpto"):
        resolve_env()


def test_load_aws_config_no_modo_local_recusa_com_mensagem_clara(monkeypatch):
    monkeypatch.setenv("ENV", "local")

    with pytest.raises(ValueError, match="modo aws"):
        load_aws_config()


def test_load_aws_config_no_modo_aws_exige_regiao(monkeypatch):
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.delenv("AWS_REGION", raising=False)

    with pytest.raises(ValueError, match="AWS_REGION"):
        load_aws_config()


def test_load_aws_config_no_modo_aws_resolve_regiao(monkeypatch):
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    cfg = load_aws_config()

    assert cfg.env == "aws"
    assert cfg.region == "us-east-1"


def test_get_client_recusa_servico_fora_dos_dois_permitidos(monkeypatch):
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    with pytest.raises(ValueError, match="s3"):
        get_client("s3")


@pytest.mark.parametrize("service", ["textract", "rekognition"])
def test_get_client_cria_os_dois_servicos_permitidos(monkeypatch, service):
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    client = get_client(service)

    assert client.meta.region_name == "us-east-1"
    assert service in client.meta.endpoint_url
