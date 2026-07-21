from pipelines.prescription.models import PrescriptionRecord
from pipelines.prescription.rules import check_abrupt_change, check_dose_range


def _record(drug="paracetamol", dose=500, unit="mg", patient_id="p1", ts="2026-01-01T00:00:00"):
    return PrescriptionRecord(
        patient_id=patient_id, drug=drug, dose=dose, unit=unit, frequency="8/8h", timestamp=ts
    )


def test_dose_dentro_da_faixa_e_normal():
    result = check_dose_range(_record(dose=500))
    assert result.kind == "normal"


def test_dose_abaixo_da_faixa_e_anomala():
    result = check_dose_range(_record(dose=100))
    assert result.kind == "dose_fora_de_faixa"


def test_dose_acima_da_faixa_e_anomala():
    result = check_dose_range(_record(dose=5000))
    assert result.kind == "dose_fora_de_faixa"


def test_medicamento_fora_do_catalogo_e_sem_referencia():
    result = check_dose_range(_record(drug="medicamento-inexistente-xyz"))
    assert result.kind == "sem_referencia"


def test_primeiro_registro_sem_historico_e_normal():
    result = check_abrupt_change(_record(dose=500), previous=None)
    assert result.kind == "normal"


def test_variacao_exatamente_no_threshold_nao_e_anomala():
    previous = _record(dose=400)
    current = _record(dose=600)  # variação de exatamente 50%
    result = check_abrupt_change(current, previous, threshold=0.5)
    assert result.kind == "normal"


def test_variacao_acima_do_threshold_e_anomala():
    previous = _record(dose=400)
    current = _record(dose=601)  # variação > 50%
    result = check_abrupt_change(current, previous, threshold=0.5)
    assert result.kind == "mudanca_abrupta"


def test_variacao_pequena_e_normal():
    previous = _record(dose=500)
    current = _record(dose=520)
    result = check_abrupt_change(current, previous)
    assert result.kind == "normal"
