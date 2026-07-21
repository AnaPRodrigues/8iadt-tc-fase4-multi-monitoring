"""Testes de AwsConfig/load_aws_config (AWSF-01, AWSF-02)."""

import pytest

from aws.clients import load_aws_config


def test_env_local_completo_resolve_config(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")

    cfg = load_aws_config()

    assert cfg.env == "local"
    assert cfg.region == "us-east-1"
    assert cfg.endpoint_url == "http://localhost:4566"


def test_env_cloud_completo_resolve_sem_endpoint(monkeypatch):
    monkeypatch.setenv("ENV", "cloud")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("LOCALSTACK_ENDPOINT", raising=False)

    cfg = load_aws_config()

    assert cfg.env == "cloud"
    assert cfg.endpoint_url is None


def test_env_invalido_nomeia_o_valor_recebido(monkeypatch):
    monkeypatch.setenv("ENV", "xpto")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    with pytest.raises(ValueError, match="xpto"):
        load_aws_config()


def test_env_local_sem_endpoint_nomeia_a_variavel_ausente(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("LOCALSTACK_ENDPOINT", raising=False)

    with pytest.raises(ValueError, match="LOCALSTACK_ENDPOINT"):
        load_aws_config()


def test_aws_region_ausente_nomeia_a_variavel(monkeypatch):
    monkeypatch.setenv("ENV", "cloud")
    monkeypatch.delenv("AWS_REGION", raising=False)

    with pytest.raises(ValueError, match="AWS_REGION"):
        load_aws_config()


def test_env_ausente_nomeia_a_variavel(monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    with pytest.raises(ValueError, match="ENV"):
        load_aws_config()


def test_config_e_imutavel(monkeypatch):
    monkeypatch.setenv("ENV", "cloud")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    cfg = load_aws_config()

    with pytest.raises(AttributeError):
        cfg.env = "local"
