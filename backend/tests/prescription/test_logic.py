"""Processamento de ponta a ponta da prescrição no modo local (pdfplumber).

Sem Docker e sem nuvem: gera um PDF sintético real, roda `logic.process` e
verifica a extração, as regras clínicas e a evidência. A prescrição anterior
(para a regra de variação abrupta) é injetada por parâmetro.
"""

import pytest

from pipelines.prescription.generator import generate_prescription
from pipelines.prescription.logic import process
from pipelines.prescription.models import PrescriptionRecord


@pytest.fixture(autouse=True)
def _modo_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")


def test_prescricao_normal_sem_anomalia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # evidência (se houver) não polui o repo
    pdf = generate_prescription("p-1", "losartana", dose=50, frequency="1x/dia", seed=1)

    resultado = process(pdf, source_id="presc_p1.pdf")

    assert resultado.parse_failure is None
    assert resultado.record.patient_id == "p-1"
    assert resultado.record.drug == "losartana"
    assert resultado.record.dose == 50.0
    assert resultado.anomalies == []
    assert resultado.evidence_id is None


def test_dose_fora_da_faixa_gera_anomalia_e_evidencia(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # faixa da losartana é 25–100 mg; 250 está muito acima
    pdf = generate_prescription("p-2", "losartana", dose=250, frequency="1x/dia", seed=2)

    resultado = process(pdf, source_id="presc_p2.pdf")

    tipos = {a.kind for a in resultado.anomalies}
    assert "dose_fora_de_faixa" in tipos
    assert resultado.evidence_id is not None


def test_variacao_abrupta_detectada_com_prescricao_anterior_injetada(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    anterior = PrescriptionRecord(
        patient_id="p-3",
        drug="losartana",
        dose=50.0,
        unit="mg",
        frequency="1x/dia",
        timestamp="2026-01-01T00:00:00",
    )
    # 100 mg está na faixa, mas é +100% em relação à dose anterior (50 mg)
    pdf = generate_prescription("p-3", "losartana", dose=100, frequency="1x/dia", seed=3)

    resultado = process(pdf, source_id="presc_p3.pdf", previous_record=anterior)

    tipos = {a.kind for a in resultado.anomalies}
    assert "mudanca_abrupta" in tipos
    assert "dose_fora_de_faixa" not in tipos  # 100 mg está dentro da faixa
    assert resultado.evidence_id is not None


def test_pdf_ilegivel_reporta_falha_de_leitura_sem_quebrar(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resultado = process(b"isto nao e um PDF", source_id="lixo.pdf")

    assert resultado.parse_failure is not None
    assert resultado.record is None
    assert resultado.anomalies == []
