"""Precision/recall por tipo de anomalia, contra o ground truth do gerador.

Este módulo reaplica `rules.check_dose_range`/`check_abrupt_change` a cada
registro e compara com o rótulo conhecido do gerador. Registros "sem_referencia"
(medicamento fora do catálogo) são excluídos do cálculo de dose, nunca contados
como falso positivo/negativo (indefinido não é a mesma coisa que zero).
"""

from collections import defaultdict
from pathlib import Path

from common.metrics import MetricsReport, binary_metrics, save_report
from pipelines.prescription import rules
from pipelines.prescription.models import GroundTruthEntry, PrescriptionRecord


def evaluate(
    ground_truth: list[GroundTruthEntry], records: list[PrescriptionRecord]
) -> dict[str, MetricsReport]:
    """Compara o veredito das duas regras com o ground truth conhecido.

    Casa cada rótulo ao registro exato por `(patient_id, drug, timestamp)` — em
    sequências de mudança abrupta o mesmo paciente/medicamento aparece mais de
    uma vez, então `(patient_id, drug)` sozinho não identifica o registro certo.
    """
    records_by_key = {(r.patient_id, r.drug, r.timestamp): r for r in records}

    by_patient_drug: dict[tuple[str, str], list[PrescriptionRecord]] = defaultdict(list)
    for record in records:
        by_patient_drug[(record.patient_id, record.drug)].append(record)
    for sequence in by_patient_drug.values():
        sequence.sort(key=lambda r: r.timestamp)

    dose_true: list[bool] = []
    dose_pred: list[bool] = []
    abrupt_true: list[bool] = []
    abrupt_pred: list[bool] = []

    for entry in ground_truth:
        record = records_by_key.get((entry.patient_id, entry.drug, entry.timestamp))
        if record is None:
            continue

        dose_result = rules.check_dose_range(record)
        if dose_result.kind != "sem_referencia":
            dose_true.append(entry.anomaly_type == "dose_fora_de_faixa")
            dose_pred.append(dose_result.kind == "dose_fora_de_faixa")

        sequence = by_patient_drug[(entry.patient_id, entry.drug)]
        index = sequence.index(record)
        previous = sequence[index - 1] if index > 0 else None
        if previous is not None:
            abrupt_result = rules.check_abrupt_change(record, previous)
            abrupt_true.append(entry.anomaly_type == "mudanca_abrupta")
            abrupt_pred.append(abrupt_result.kind == "mudanca_abrupta")

    return {
        "dose_fora_de_faixa": binary_metrics(dose_true, dose_pred, detector="dose_fora_de_faixa"),
        "mudanca_abrupta": binary_metrics(abrupt_true, abrupt_pred, detector="mudanca_abrupta"),
    }


def save_evaluation(reports: dict[str, MetricsReport], output_dir: Path) -> None:
    """Persiste um relatório JSON por detector em `output_dir/<detector>.json`."""
    output_dir = Path(output_dir)
    for name, report in reports.items():
        save_report(report, output_dir / f"{name}.json")
