"""Testes de integração de history.py contra LocalStack real (DynamoDB).

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566.
"""

import socket
import uuid

import pytest

from aws.provision import ensure_table
from pipelines.prescription import history
from pipelines.prescription.models import PrescriptionRecord


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


def _record(patient_id="p1", drug="paracetamol", dose=500.0, timestamp="2026-01-01T00:00:00"):
    return PrescriptionRecord(
        patient_id=patient_id,
        drug=drug,
        dose=dose,
        unit="mg",
        frequency="8/8h",
        timestamp=timestamp,
    )


def test_save_record_grava_e_get_latest_recupera(table):
    record = _record()
    dedup = history.dedup_key("bucket", "key.pdf", "etag-1")

    saved = history.save_record(record, dedup)

    assert saved is True
    latest = history.get_latest(record.patient_id, record.drug)
    assert latest == record


def test_save_record_mesmo_dedup_key_nao_duplica(table):
    record = _record()
    dedup = history.dedup_key("bucket", "key.pdf", "etag-1")

    primeira = history.save_record(record, dedup)
    segunda = history.save_record(record, dedup)

    assert primeira is True
    assert segunda is False


def test_get_latest_sem_historico_devolve_none(table):
    assert history.get_latest("paciente-inexistente", "paracetamol") is None


def test_get_latest_devolve_o_mais_recente(table):
    antigo = _record(timestamp="2026-01-01T00:00:00")
    recente = _record(timestamp="2026-01-02T00:00:00")

    history.save_record(antigo, history.dedup_key("b", "k1.pdf", "etag-a"))
    history.save_record(recente, history.dedup_key("b", "k2.pdf", "etag-b"))

    latest = history.get_latest(antigo.patient_id, antigo.drug)
    assert latest == recente
