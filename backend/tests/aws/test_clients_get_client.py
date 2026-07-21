"""Testes de get_client (AWSF-01, AWSF-07)."""

from aws.clients import AwsConfig, get_client


def test_get_client_local_resolve_endpoint_localstack():
    cfg = AwsConfig(env="local", region="us-east-1", endpoint_url="http://localhost:4566")

    client = get_client("s3", cfg)

    assert client.meta.endpoint_url == "http://localhost:4566"
    assert client.meta.region_name == "us-east-1"


def test_get_client_cloud_resolve_sem_endpoint_localstack():
    cfg = AwsConfig(env="cloud", region="us-east-1", endpoint_url=None)

    client = get_client("s3", cfg)

    assert "localhost" not in client.meta.endpoint_url
    assert "4566" not in client.meta.endpoint_url
    assert client.meta.region_name == "us-east-1"


def test_get_client_usa_load_aws_config_quando_config_omitida(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")

    client = get_client("sns")

    assert client.meta.endpoint_url == "http://localhost:4566"


def test_get_client_local_com_regiao_diferente():
    """Prova que a região vem da config, não de uma constante fixa no factory."""
    cfg = AwsConfig(env="local", region="sa-east-1", endpoint_url="http://localhost:4566")

    client = get_client("dynamodb", cfg)

    assert client.meta.region_name == "sa-east-1"
