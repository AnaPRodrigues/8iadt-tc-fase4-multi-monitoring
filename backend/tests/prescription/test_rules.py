from pipelines.prescription.models import PrescriptionRecord
from pipelines.prescription.rules import check_abrupt_change, check_dose_range, regulatory_info


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


# --- PRESC-01, PRESC-02: regulatory_info (spec final-fix) ---

def test_regulatory_info_medicamento_controlado():
    """PRESC-01: morfina devolve A1, controlado, com princípio ativo e fonte."""
    info = regulatory_info(_record(drug="morfina", dose=10))
    assert info["control_category"] == "A1"
    assert info["is_controlled"] is True
    assert "morfina" in info["active_ingredient"].lower()
    assert "ANVISA" in info["source"]


def test_regulatory_info_medicamento_nao_controlado():
    """PRESC-01: paracetamol não é controlado, mas tem princípio ativo."""
    info = regulatory_info(_record(drug="paracetamol", dose=500))
    assert info["is_controlled"] is False
    assert info["control_category"] == ""
    assert len(info["active_ingredient"]) > 0


def test_regulatory_info_medicamento_fora_do_catalogo():
    """PRESC-02: fora do catálogo → source='não verificado'."""
    info = regulatory_info(_record(drug="medicamento-inexistente-xyz"))
    assert info["source"] == "não verificado"
    assert info["is_controlled"] is False
    assert info["control_category"] == ""


def test_regulatory_info_tem_dose_de_referencia():
    """PRESC-01: reference_dose no formato 'min–max unidade'."""
    info = regulatory_info(_record(drug="digoxina", dose=0.25))
    assert "0.125" in info["reference_dose"]
    assert "0.5" in info["reference_dose"]
    assert "mg" in info["reference_dose"]
