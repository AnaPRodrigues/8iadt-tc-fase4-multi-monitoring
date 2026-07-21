"""Testes de integração de logic.py e handler.py contra LocalStack real.

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566.
"""

import socket
import uuid

import pytest
from botocore.exceptions import ClientError

from aws.clients import get_client
from aws.provision import ensure_bucket, ensure_table
from pipelines.prescription.generator import generate_prescription
from pipelines.prescription.handler import lambda_handler
from pipelines.prescription.logic import process


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


@pytest.fixture(autouse=True)
def _env_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


@pytest.fixture
def table(monkeypatch):
    nome = f"mm-test-prescription-{uuid.uuid4().hex[:8]}"
    ensure_table(nome)
    monkeypatch.setenv("DYNAMODB_TABLE", nome)
    return nome


@pytest.fixture
def bucket():
    nome = f"mm-test-prescription-bucket-{uuid.uuid4().hex[:8]}"
    ensure_bucket(nome)
    return nome


def _s3_event(bucket: str, key: str, etag: str) -> dict:
    return {
        "Records": [
            {"s3": {"bucket": {"name": bucket}, "object": {"key": key, "eTag": etag}}}
        ]
    }


# ---------- logic.process ----------


def test_process_dose_normal_sem_anomalias(table):
    pdf_bytes = generate_prescription(
        patient_id="p1", drug="paracetamol", dose=500, frequency="8/8h", seed=1
    )
    result = process(pdf_bytes, bucket="b", key="k1.pdf", etag="etag-1")

    assert result.parse_failure is None
    assert result.anomalies == []
    assert result.evidence_id is None
    assert result.deduplicated is False
    assert result.record.patient_id == "p1"


def test_process_dose_fora_de_faixa_gera_evidencia(table):
    pdf_bytes = generate_prescription(
        patient_id="p2", drug="paracetamol", dose=50000, frequency="8/8h", seed=2
    )
    result = process(pdf_bytes, bucket="b", key="k2.pdf", etag="etag-2")

    assert result.parse_failure is None
    assert any(a.kind == "dose_fora_de_faixa" for a in result.anomalies)
    assert result.evidence_id is not None


def test_process_mudanca_abrupta_entre_duas_prescricoes(table):
    primeira = generate_prescription(
        patient_id="p3", drug="losartana", dose=50, frequency="1/dia", seed=10
    )
    process(primeira, bucket="b", key="k3a.pdf", etag="etag-3a")

    segunda = generate_prescription(
        patient_id="p3", drug="losartana", dose=100, frequency="1/dia", seed=11
    )
    result = process(segunda, bucket="b", key="k3b.pdf", etag="etag-3b")

    assert any(a.kind == "mudanca_abrupta" for a in result.anomalies)


def test_process_evento_duplicado_nao_reprocessa(table):
    pdf_bytes = generate_prescription(
        patient_id="p4", drug="paracetamol", dose=500, frequency="8/8h", seed=4
    )
    primeiro = process(pdf_bytes, bucket="b", key="k4.pdf", etag="etag-4")
    segundo = process(pdf_bytes, bucket="b", key="k4.pdf", etag="etag-4")

    assert primeiro.deduplicated is False
    assert segundo.deduplicated is True


def test_process_medicamento_fora_do_catalogo_e_sem_referencia(table):
    pdf_bytes = generate_prescription(
        patient_id="p5", drug="medicamento-inexistente-xyz", dose=10, frequency="1/dia", seed=5
    )
    result = process(pdf_bytes, bucket="b", key="k5.pdf", etag="etag-5")

    assert any(a.kind == "sem_referencia" for a in result.anomalies)


# ---------- handler.lambda_handler ----------


def test_handler_processa_evento_s3_real(table, bucket):
    pdf_bytes = generate_prescription(
        patient_id="p6", drug="paracetamol", dose=500, frequency="8/8h", seed=6
    )
    client = get_client("s3")
    key = "prescricoes/p6.pdf"
    client.put_object(Bucket=bucket, Key=key, Body=pdf_bytes)
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    response = lambda_handler(_s3_event(bucket, key, etag), context=None)

    assert response["statusCode"] == 200
    # objeto processado com sucesso continua no lugar original
    client.head_object(Bucket=bucket, Key=key)


def test_handler_pdf_ilegivel_move_para_errors(table, bucket):
    client = get_client("s3")
    key = "prescricoes/corrompido.pdf"
    client.put_object(Bucket=bucket, Key=key, Body=b"isto nao e um pdf valido")
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    response = lambda_handler(_s3_event(bucket, key, etag), context=None)

    assert response["statusCode"] == 200
    with pytest.raises(ClientError):
        client.head_object(Bucket=bucket, Key=key)
    client.head_object(Bucket=bucket, Key=f"errors/{key}")


def test_handler_evento_sem_records_nao_falha():
    response = lambda_handler({"Records": []}, context=None)
    assert response["statusCode"] == 200


def test_handler_loga_arquivo_resultado_e_tipo_de_anomalia(table, bucket, caplog):
    pdf_bytes = generate_prescription(
        patient_id="p7", drug="paracetamol", dose=50000, frequency="8/8h", seed=7
    )
    client = get_client("s3")
    key = "prescricoes/p7.pdf"
    client.put_object(Bucket=bucket, Key=key, Body=pdf_bytes)
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    with caplog.at_level("INFO", logger="mm.prescription.handler"):
        lambda_handler(_s3_event(bucket, key, etag), context=None)

    assert bucket in caplog.text
    assert key in caplog.text
    assert "dose_fora_de_faixa" in caplog.text


def test_handler_lote_com_um_corrompido_e_um_valido_processa_ambos(table, bucket):
    client = get_client("s3")

    key_valido = "prescricoes/valido.pdf"
    pdf_bytes = generate_prescription(
        patient_id="p8", drug="paracetamol", dose=500, frequency="8/8h", seed=8
    )
    client.put_object(Bucket=bucket, Key=key_valido, Body=pdf_bytes)
    etag_valido = client.head_object(Bucket=bucket, Key=key_valido)["ETag"]

    key_corrompido = "prescricoes/corrompido.pdf"
    client.put_object(Bucket=bucket, Key=key_corrompido, Body=b"nao e um pdf valido")
    etag_corrompido = client.head_object(Bucket=bucket, Key=key_corrompido)["ETag"]

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key_corrompido, "eTag": etag_corrompido},
                }
            },
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key_valido, "eTag": etag_valido},
                }
            },
        ]
    }

    response = lambda_handler(event, context=None)

    assert response["statusCode"] == 200
    # o corrompido foi movido para errors/, mas isso não travou o processamento do válido
    client.head_object(Bucket=bucket, Key=f"errors/{key_corrompido}")
    client.head_object(Bucket=bucket, Key=key_valido)

    ddb = get_client("dynamodb")
    resp = ddb.query(
        TableName=table,
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": {"S": "PATIENT#p8#DRUG#paracetamol"}},
    )
    assert len(resp["Items"]) == 1
