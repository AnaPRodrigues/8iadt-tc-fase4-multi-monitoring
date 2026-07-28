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
    }
