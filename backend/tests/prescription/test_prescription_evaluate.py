from pipelines.prescription.adapters import PdfplumberExtractor
from pipelines.prescription.evaluate import evaluate
from pipelines.prescription.generator import generate_dataset
from pipelines.prescription.models import GroundTruthEntry, PrescriptionRecord
from pipelines.prescription.parser import parse_prescription


def _records_from_dataset(dataset):
    records = []
    for pdf_bytes, _entry in dataset:
        extracted = PdfplumberExtractor().extract(pdf_bytes)
        record = parse_prescription(extracted)
        records.append(record)
    return records


def test_evaluate_bate_com_ground_truth_misto():
    dataset = generate_dataset(n=30, seed=42, anomaly_rate=0.4)
    ground_truth = [entry for _, entry in dataset]
    records = _records_from_dataset(dataset)

    report = evaluate(ground_truth, records)

    # rules.check_dose_range usa o mesmo catálogo que o gerador -- deveria
    # reproduzir o rótulo exatamente.
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.support == sum(1 for e in ground_truth if e.is_anomalous)


def test_evaluate_exclui_sem_referencia_do_calculo():
    ground_truth = [
        GroundTruthEntry(
            patient_id="p1", drug="paracetamol", dose=500, is_anomalous=False, anomaly_type=None
        ),
        GroundTruthEntry(
            patient_id="p2",
            drug="medicamento-inexistente-xyz",
            dose=10,
            is_anomalous=False,
            anomaly_type=None,
        ),
    ]
    records = [
        PrescriptionRecord(
            patient_id="p1",
            drug="paracetamol",
            dose=500,
            unit="mg",
            frequency="8/8h",
            timestamp="2026-01-01T00:00:00",
        ),
        PrescriptionRecord(
            patient_id="p2",
            drug="medicamento-inexistente-xyz",
            dose=10,
            unit="mg",
            frequency="8/8h",
            timestamp="2026-01-01T00:00:00",
        ),
    ]

    report = evaluate(ground_truth, records)

    assert report.support == 0  # p2 (sem_referencia) excluído; só sobra p1 (normal)


def test_evaluate_sem_anomalos_recall_indefinido():
    ground_truth = [
        GroundTruthEntry(
            patient_id="p1", drug="paracetamol", dose=500, is_anomalous=False, anomaly_type=None
        )
    ]
    records = [
        PrescriptionRecord(
            patient_id="p1",
            drug="paracetamol",
            dose=500,
            unit="mg",
            frequency="8/8h",
            timestamp="2026-01-01T00:00:00",
        )
    ]

    report = evaluate(ground_truth, records)

    assert report.support == 0
    assert report.recall is None
