"""Regras de anomalia sobre um ``PrescriptionRecord`` (PRESC-12, PRESC-13, PRESC-14).

Um medicamento fora do catálogo nunca é classificado como normal ou anômalo por
omissão — vira ``"sem_referencia"`` e é excluído das métricas de avaliação
(mesmo princípio de VITALS-10: indefinido não é a mesma coisa que zero).
"""

from collections.abc import Callable

from pipelines.prescription import catalog
from pipelines.prescription.models import AnomalyResult, DrugRange, PrescriptionRecord

ABRUPT_CHANGE_THRESHOLD = 0.5


def check_dose_range(
    record: PrescriptionRecord,
    lookup: Callable[[str], DrugRange | None] = catalog.lookup,
) -> AnomalyResult:
    """Classifica a dose do registro em relação à faixa terapêutica do catálogo."""
    drug_range = lookup(record.drug)
    if drug_range is None:
        return AnomalyResult(
            kind="sem_referencia",
            detail=f"medicamento '{record.drug}' fora do catálogo",
        )
    if record.dose < drug_range.min_dose or record.dose > drug_range.max_dose:
        return AnomalyResult(
            kind="dose_fora_de_faixa",
            detail=(
                f"dose {record.dose}{record.unit} fora da faixa "
                f"[{drug_range.min_dose}, {drug_range.max_dose}]{drug_range.unit}"
            ),
        )
    return AnomalyResult(kind="normal", detail="dose dentro da faixa terapêutica")


def check_abrupt_change(
    record: PrescriptionRecord,
    previous: PrescriptionRecord | None,
    threshold: float = ABRUPT_CHANGE_THRESHOLD,
) -> AnomalyResult:
    """Compara a dose atual com a do registro anterior do mesmo paciente/medicamento."""
    if previous is None:
        return AnomalyResult(kind="normal", detail="sem histórico anterior")

    relative_change = abs(record.dose - previous.dose) / previous.dose
    if relative_change > threshold:
        return AnomalyResult(
            kind="mudanca_abrupta",
            detail=(
                f"variação de {relative_change:.0%} em relação à dose anterior "
                f"({previous.dose}{previous.unit} -> {record.dose}{record.unit})"
            ),
        )
    return AnomalyResult(kind="normal", detail="variação dentro do esperado")
