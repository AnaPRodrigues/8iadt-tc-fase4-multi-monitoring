"""Precision/recall do detector de dose fora de faixa contra o ground truth (PRESC-10).

O DynamoDB não persiste o veredito da regra, só o registro em si — este módulo
reaplica `rules.check_dose_range` a cada registro e compara com o rótulo
conhecido do gerador. Registros "sem_referencia" (medicamento fora do catálogo)
são excluídos do cálculo, nunca contados como falso positivo/negativo (mesmo
princípio de VITALS-10: indefinido não é a mesma coisa que zero).
"""

from common.metrics import MetricsReport, binary_metrics
from pipelines.prescription import rules
from pipelines.prescription.models import GroundTruthEntry, PrescriptionRecord


def evaluate(
    ground_truth: list[GroundTruthEntry], records: list[PrescriptionRecord]
) -> MetricsReport:
    """Compara o veredito de `check_dose_range` com o ground truth conhecido."""
    records_by_patient_drug = {(r.patient_id, r.drug): r for r in records}

    y_true: list[bool] = []
    y_pred: list[bool] = []

    for entry in ground_truth:
        record = records_by_patient_drug.get((entry.patient_id, entry.drug))
        if record is None:
            continue

        result = rules.check_dose_range(record)
        if result.kind == "sem_referencia":
            continue

        y_true.append(entry.is_anomalous)
        y_pred.append(result.kind == "dose_fora_de_faixa")

    return binary_metrics(y_true, y_pred, detector="dose_fora_de_faixa")
