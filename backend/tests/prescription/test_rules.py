from pipelines.prescription.models import PrescriptionRecord
from pipelines.prescription.rules import check_abrupt_change, check_dose_range, evaluate_prescription, regulatory_info


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


# --- PRESC-11: check_high_risk_substitution (spec prescription-criticality) ---

from pipelines.prescription.rules import check_high_risk_substitution


def test_substituicao_salto_2_niveis_deteta_critica():
    """PRESC-11: dipirona(crit=1) → morfina(crit=3) = substituicao_critica."""
    previous = _record(drug="dipirona")
    current = _record(drug="morfina")
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "substituicao_critica"
    assert "Dipirona" in result.reason
    assert "Morfina" in result.reason
    assert "nível 1" in result.reason
    assert "nível 3" in result.reason


def test_substituicao_salto_1_nivel_para_2_nao_deteta():
    """PRESC-11: paracetamol(crit=1) → tramadol(crit=2) = normal (delta=1 < 2)."""
    previous = _record(drug="paracetamol")
    current = _record(drug="tramadol")
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "normal"


def test_substituicao_salto_1_para_3_deteta_critica():
    """PRESC-11: ibuprofeno(crit=1) → fentanil(crit=3) = substituicao_critica (delta=2)."""
    previous = _record(drug="ibuprofeno")
    current = _record(drug="fentanil")
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "substituicao_critica"


def test_substituicao_mesmo_nivel_nao_deteta():
    """PRESC-11: morfina(crit=3) → fentanil(crit=3) = normal."""
    previous = _record(drug="morfina")
    current = _record(drug="fentanil")
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "normal"


def test_substituicao_mesmo_farmaco_nao_deteta():
    """PRESC-11: mesmo fármaco = normal (não é substituição)."""
    previous = _record(drug="paracetamol", dose=500)
    current = _record(drug="paracetamol", dose=1000)
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "normal"


def test_substituicao_sem_historico_nao_deteta():
    """PRESC-11: sem prescrição anterior = normal."""
    result = check_high_risk_substitution(_record(drug="morfina"), previous=None)
    assert result.kind == "normal"


def test_substituicao_farmaco_fora_do_catalogo():
    """PRESC-11: fármaco atual fora do catálogo = sem_referencia."""
    previous = _record(drug="dipirona")
    current = _record(drug="medicamento-inventado-xyz")
    result = check_high_risk_substitution(current, previous)
    assert result.kind == "sem_referencia"


def test_substituicao_farmaco_anterior_fora_do_catalogo():
    """PRESC-11: fármaco anterior fora do catálogo → assume criticality=0, deteta se atual ≥2."""
    previous = _record(drug="medicamento-inventado-xyz")
    current = _record(drug="morfina")
    result = check_high_risk_substitution(current, previous)
    # previous desconhecido → assume criticality=0; atual=3 → salto ≥2 → crítico
    assert result.kind == "substituicao_critica"


# --- PRESC-12: evaluate_prescription (spec prescription-criticality) ---

def test_evaluate_prescription_dose_fora_de_faixa_primeiro_que_substituicao():
    """PRESC-12: dose_fora_de_faixa deve vir antes de substituicao_critica (mais grave).

    dipirona(crit=1, faixa 500–1000mg) → morfina 200mg(crit=3, faixa 10–60mg):
    dispara dose_fora_de_faixa (200 fora de [10,60]) E substituicao_critica
    (salto crit=1→3). O resultado de dose deve aparecer antes na lista.
    """
    previous = _record(drug="dipirona", dose=500)
    # morfina 200mg — fora da faixa [10, 60] E salto de crit 1→3
    current = _record(drug="morfina", dose=200, unit="mg")
    results = evaluate_prescription(current, previous)

    # a lista deve ter as 3 regras: [dose, substituicao, mudanca_abrupta]
    kinds = [r.kind for r in results]
    assert kinds[0] == "dose_fora_de_faixa", (
        f"dose_fora_de_faixa devia ser o primeiro (mais grave), mas a ordem foi {kinds}"
    )
    assert "substituicao_critica" in kinds
    # mudanca_abrupta não se aplica (fármacos diferentes)
    assert kinds[2] == "normal"


def test_evaluate_prescription_sem_anomalias_todas_regras_normal():
    """PRESC-12: sem anomalias → todos os resultados têm kind='normal'.

    paracetamol 500mg está na faixa [500, 1000]; sem histórico não dispara
    nem substituição nem variação abrupta.
    """
    results = evaluate_prescription(_record(drug="paracetamol", dose=500), previous=None)

    assert len(results) == 3  # dose, substituicao, mudanca_abrupta
    for r in results:
        assert r.kind == "normal", (
            f"esperado 'normal' para todas as regras, mas obteve kind='{r.kind}': {r.reason}"
        )
