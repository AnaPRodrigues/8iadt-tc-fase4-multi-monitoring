import json

from pipelines.prescription.adapters import PdfplumberExtractor
from pipelines.prescription.evaluate import evaluate, save_evaluation
from pipelines.prescription.generator import generate_dataset, generate_sequence_dataset
from pipelines.prescription.models import GroundTruthEntry, PrescriptionRecord
from pipelines.prescription.parser import parse_prescription


def _records_from_dataset(dataset):
    records = []
    for pdf_bytes, _entry in dataset:
        extracted = PdfplumberExtractor().extract(pdf_bytes)
        record = parse_prescription(extracted)
        records.append(record)
    return records


def test_evaluate_dose_fora_de_faixa_bate_com_ground_truth_misto():
    dataset = generate_dataset(n=30, seed=42, anomaly_rate=0.4)
    ground_truth = [entry for _, entry in dataset]
    records = _records_from_dataset(dataset)

    reports = evaluate(ground_truth, records)

    # rules.check_dose_range usa o mesmo catálogo que o gerador -- deveria
    # reproduzir o rótulo exatamente.
    report = reports["dose_fora_de_faixa"]
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.support == sum(1 for e in ground_truth if e.anomaly_type == "dose_fora_de_faixa")


def test_evaluate_mudanca_abrupta_bate_com_ground_truth_de_sequencias():
    dataset = generate_sequence_dataset(n_sequences=15, seed=7, abrupt_rate=0.5)
    ground_truth = [entry for _, entry in dataset]
    records = _records_from_dataset(dataset)

    reports = evaluate(ground_truth, records)

    report = reports["mudanca_abrupta"]
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.support == sum(1 for e in ground_truth if e.anomaly_type == "mudanca_abrupta")


def test_evaluate_primeiro_registro_da_sequencia_nunca_conta_para_abrupta():
    # cada sequência tem 2 entradas; só a segunda tem "previous" -- support de
    # mudanca_abrupta nunca deveria contar a primeira (baseline) de cada par.
    dataset = generate_sequence_dataset(n_sequences=5, seed=1, abrupt_rate=1.0)
    ground_truth = [entry for _, entry in dataset]
    records = _records_from_dataset(dataset)

    reports = evaluate(ground_truth, records)

    assert reports["mudanca_abrupta"].support == 5  # só as 5 "seguintes", nunca as 5 baselines


def test_evaluate_exclui_sem_referencia_do_calculo():
    # Se "sem_referencia" NÃO for excluído, p3 vira um falso negativo do detector
    # de dose (rótulo diz anômalo, veredito "sem_referencia" != "dose_fora_de_faixa"),
    # derrubando o recall de 1.0 para 0.5 -- distingue a exclusão de verdade,
    # não só um support que ficaria 0 de qualquer jeito.
    ground_truth = [
        GroundTruthEntry(
            patient_id="p1",
            drug="paracetamol",
            dose=500,
            is_anomalous=False,
            anomaly_type=None,
            timestamp="2026-01-01T00:00:00",
        ),
        GroundTruthEntry(
            patient_id="p2",
            drug="paracetamol",
            dose=50000,
            is_anomalous=True,
            anomaly_type="dose_fora_de_faixa",
            timestamp="2026-01-01T00:00:00",
        ),
        GroundTruthEntry(
            patient_id="p3",
            drug="medicamento-inexistente-xyz",
            dose=10,
            is_anomalous=True,
            anomaly_type="dose_fora_de_faixa",
            timestamp="2026-01-01T00:00:00",
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
            drug="paracetamol",
            dose=50000,
            unit="mg",
            frequency="8/8h",
            timestamp="2026-01-01T00:00:00",
        ),
        PrescriptionRecord(
            patient_id="p3",
            drug="medicamento-inexistente-xyz",
            dose=10,
            unit="mg",
            frequency="8/8h",
            timestamp="2026-01-01T00:00:00",
        ),
    ]

    reports = evaluate(ground_truth, records)

    assert reports["dose_fora_de_faixa"].support == 1  # só p2; p3 (sem_referencia) excluído
    assert reports["dose_fora_de_faixa"].recall == 1.0


def test_save_evaluation_persiste_um_arquivo_json_por_detector(tmp_path):
    dataset = generate_dataset(n=10, seed=3, anomaly_rate=0.4)
    ground_truth = [entry for _, entry in dataset]
    records = _records_from_dataset(dataset)
    reports = evaluate(ground_truth, records)

    save_evaluation(reports, tmp_path)

    dose_path = tmp_path / "dose_fora_de_faixa.json"
    abrupt_path = tmp_path / "mudanca_abrupta.json"
    assert dose_path.is_file()
    assert abrupt_path.is_file()

    saved_dose = json.loads(dose_path.read_text())
    assert saved_dose["detector"] == "dose_fora_de_faixa"
    assert saved_dose["precision"] == reports["dose_fora_de_faixa"].precision
    assert saved_dose["support"] == reports["dose_fora_de_faixa"].support


def test_evaluate_sem_anomalos_recall_indefinido():
    ground_truth = [
        GroundTruthEntry(
            patient_id="p1",
            drug="paracetamol",
            dose=500,
            is_anomalous=False,
            anomaly_type=None,
            timestamp="2026-01-01T00:00:00",
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

    reports = evaluate(ground_truth, records)

    assert reports["dose_fora_de_faixa"].support == 0
    assert reports["dose_fora_de_faixa"].recall is None
