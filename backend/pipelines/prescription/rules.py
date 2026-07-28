"""Regras de anomalia sobre um ``PrescriptionRecord``.

Um medicamento fora do catálogo nunca é classificado como normal ou anômalo por
omissão — vira ``"sem_referencia"`` e é excluído das métricas de avaliação
(indefinido não é a mesma coisa que zero).
"""

from collections.abc import Callable

from pipelines.prescription import catalog
from pipelines.prescription.models import AnomalyResult, DrugRange, PrescriptionRecord

ABRUPT_CHANGE_THRESHOLD = 0.5


# Devolve também a DrugRange quando disponível, para enriquecer o resultado.
def _lookup_with_range(
    record: PrescriptionRecord,
    lookup_fn: Callable[[str], DrugRange | None] = catalog.lookup,
) -> tuple[DrugRange | None, AnomalyResult]:
    """Classifica a dose + devolve a DrugRange (com info regulatória)."""
    drug_range = lookup_fn(record.drug)
    if drug_range is None:
        return None, AnomalyResult(
            kind="sem_referencia",
            reason=f"medicamento '{record.drug}' fora do catálogo",
        )
    if record.dose < drug_range.min_dose or record.dose > drug_range.max_dose:
        return drug_range, AnomalyResult(
            kind="dose_fora_de_faixa",
            reason=(
                f"dose {record.dose}{record.unit} fora da faixa "
                f"[{drug_range.min_dose}, {drug_range.max_dose}]{drug_range.unit}"
            ),
        )
    return drug_range, AnomalyResult(kind="normal", reason="dose dentro da faixa terapêutica")


def check_dose_range(
    record: PrescriptionRecord,
    lookup: Callable[[str], DrugRange | None] = catalog.lookup,
) -> AnomalyResult:
    """Classifica a dose do registro em relação à faixa terapêutica do catálogo."""
    _, result = _lookup_with_range(record, lookup)
    return result


def check_abrupt_change(
    record: PrescriptionRecord,
    previous: PrescriptionRecord | None,
    threshold: float = ABRUPT_CHANGE_THRESHOLD,
) -> AnomalyResult:
    """Compara a dose atual com a do registro anterior do mesmo paciente/medicamento."""
    if previous is None:
        return AnomalyResult(kind="normal", reason="sem histórico anterior")

    relative_change = abs(record.dose - previous.dose) / previous.dose
    if relative_change > threshold:
        return AnomalyResult(
            kind="mudanca_abrupta",
            reason=(
                f"variação de {relative_change:.0%} em relação à dose anterior "
                f"({previous.dose}{previous.unit} -> {record.dose}{record.unit})"
            ),
        )
    return AnomalyResult(kind="normal", reason="variação dentro do esperado")


def regulatory_info(
    record: PrescriptionRecord,
    lookup: Callable[[str], DrugRange | None] = catalog.lookup,
) -> dict:
    """Devolve a informação regulatória completa do medicamento.

    Retorna um dicionário com active_ingredient, control_category,
    is_controlled, reference_dose e source. Campos vazios quando
    o medicamento está fora do catálogo.
    """
    drug_range = lookup(record.drug)
    if drug_range is None:
        return {
            "active_ingredient": "",
            "control_category": "",
            "is_controlled": False,
            "reference_dose": "",
            "source": "não verificado",
        }
    return {
        "active_ingredient": drug_range.active_ingredient,
        "control_category": drug_range.control_category,
        "is_controlled": drug_range.is_controlled,
        "reference_dose": f"{drug_range.min_dose}–{drug_range.max_dose} {drug_range.unit}",
        "source": drug_range.source or "não verificado",
        "criticality": drug_range.criticality,
    }


def check_high_risk_substitution(
    record: PrescriptionRecord,
    previous: PrescriptionRecord | None,
    lookup: Callable[[str], DrugRange | None] = catalog.lookup,
) -> AnomalyResult:
    """Deteta substituição por fármaco de criticidade significativamente maior.

    Considera o nível de criticidade (1-3) de cada fármaco. Se o fármaco
    atual tiver criticidade ≥2 níveis acima do anterior, emite
    ``"substituicao_critica"``. Fármacos iguais não são considerados
    substituição — a regra de variação abrupta cobre esse caso.

    Args:
        record: Prescrição atual.
        previous: Prescrição anterior do mesmo paciente (pode ser None).
        lookup: Função de busca no catálogo.

    Returns:
        AnomalyResult com kind="substituicao_critica" se o salto for ≥2
        níveis, "sem_referencia" se o fármaco atual estiver fora do
        catálogo, ou "normal".
    """
    if previous is None:
        return AnomalyResult(kind="normal", reason="sem histórico anterior")

    # Mesmo fármaco: não é substituição (check_abrupt_change cobre este caso)
    if record.drug.lower() == previous.drug.lower():
        return AnomalyResult(kind="normal", reason="mesmo fármaco — não é substituição")

    current_range = lookup(record.drug)
    if current_range is None:
        return AnomalyResult(
            kind="sem_referencia",
            reason=f"medicamento atual '{record.drug}' fora do catálogo",
        )

    previous_range = lookup(previous.drug)
    prev_crit = previous_range.criticality if previous_range else 0

    delta = current_range.criticality - prev_crit

    if delta >= 2:
        nivel_prev = f"nível {prev_crit}" if prev_crit > 0 else "desconhecido"
        return AnomalyResult(
            kind="substituicao_critica",
            reason=(
                f"Escalonamento crítico de medicação: substituição de "
                f"'{previous.drug.capitalize()}' ({nivel_prev}) por "
                f"'{record.drug.capitalize()}' "
                f"(nível {current_range.criticality}"
                + (f" - {_criticality_label(current_range.criticality)}" if current_range.criticality >= 3 else "")
                + ")."
            ),
        )

    return AnomalyResult(kind="normal", reason="substituição dentro do esperado")


def _criticality_label(level: int) -> str:
    """Rótulo descritivo para o nível de criticidade."""
    if level >= 3:
        return "Alta Vigilância"
    if level == 2:
        return "Médio Risco"
    return "Baixo Risco"


def evaluate_prescription(
    record: PrescriptionRecord,
    previous: PrescriptionRecord | None = None,
    lookup: Callable[[str], DrugRange | None] = catalog.lookup,
) -> list[AnomalyResult]:
    """Orquestra as regras de anomalia por ordem de gravidade clínica.

    1. ``check_dose_range`` — superdosagem/subdosagem (mais grave)
    2. ``check_high_risk_substitution`` — troca por fármaco mais crítico
    3. ``check_abrupt_change`` — variação percentual no mesmo fármaco

    Devolve a lista de resultados na mesma ordem. Se não houver anomalias,
    devolve uma lista com um único ``AnomalyResult(kind="normal")``.
    """
    results: list[AnomalyResult] = []

    # 1. Dose fora da faixa (mais grave)
    dose_result = check_dose_range(record, lookup)
    results.append(dose_result)

    # 2. Substituição por fármaco de maior criticidade
    sub_result = check_high_risk_substitution(record, previous, lookup)
    results.append(sub_result)

    # 3. Variação abrupta (mesmo fármaco)
    change_result = check_abrupt_change(record, previous)
    results.append(change_result)

    return results
