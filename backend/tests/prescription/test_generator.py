import io
import json

import pdfplumber

from pipelines.prescription.generator import (
    generate_dataset,
    generate_dataset_to_disk,
    generate_prescription,
    generate_sequence_dataset,
)


def test_generate_prescription_produz_pdf_com_texto_real():
    pdf_bytes = generate_prescription(
        patient_id="p1", drug="paracetamol", dose=500, frequency="8/8h", seed=1
    )
    assert pdf_bytes[:4] == b"%PDF"

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text()
    assert "paracetamol" in text.lower()
    assert "p1" in text


def test_generate_prescription_e_deterministico_por_seed():
    # reportlab embute um /ID aleatório no trailer do PDF (não determinístico
    # byte a byte) — a garantia relevante aqui é o conteúdo extraído, que é o
    # que o parser realmente consome.
    a = generate_prescription(
        patient_id="p1", drug="paracetamol", dose=500, frequency="8/8h", seed=42
    )
    b = generate_prescription(
        patient_id="p1", drug="paracetamol", dose=500, frequency="8/8h", seed=42
    )
    with pdfplumber.open(io.BytesIO(a)) as pdf:
        text_a = pdf.pages[0].extract_text()
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        text_b = pdf.pages[0].extract_text()
    assert text_a == text_b


def test_generate_dataset_determinismo_por_seed():
    dataset_a = generate_dataset(n=10, seed=7, anomaly_rate=0.3)
    dataset_b = generate_dataset(n=10, seed=7, anomaly_rate=0.3)
    labels_a = [(e.patient_id, e.drug, e.is_anomalous) for _, e in dataset_a]
    labels_b = [(e.patient_id, e.drug, e.is_anomalous) for _, e in dataset_b]
    assert labels_a == labels_b


def test_generate_dataset_tem_pelo_menos_um_anomalo():
    dataset = generate_dataset(n=20, seed=123, anomaly_rate=0.5)
    anomalous = [e for _, e in dataset if e.is_anomalous]
    normal = [e for _, e in dataset if not e.is_anomalous]
    assert len(anomalous) > 0
    assert len(normal) > 0
    assert all(e.anomaly_type == "dose_fora_de_faixa" for e in anomalous)
    assert all(e.anomaly_type is None for e in normal)


def test_generate_dataset_pdfs_sao_extraiveis(tmp_path):
    dataset = generate_dataset(n=3, seed=99, anomaly_rate=0.3)
    for pdf_bytes, entry in dataset:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = pdf.pages[0].extract_text()
        assert entry.patient_id in text
        assert entry.drug in text.lower()


def test_generate_sequence_dataset_produz_pares_por_paciente():
    dataset = generate_sequence_dataset(n_sequences=5, seed=1, abrupt_rate=0.5)
    assert len(dataset) == 10  # 2 entradas por sequência

    entries = [entry for _, entry in dataset]
    por_paciente: dict[str, list] = {}
    for entry in entries:
        por_paciente.setdefault(entry.patient_id, []).append(entry)
    assert all(len(v) == 2 for v in por_paciente.values())


def test_generate_sequence_dataset_baseline_nunca_e_anomalo():
    dataset = generate_sequence_dataset(n_sequences=10, seed=2, abrupt_rate=1.0)
    entries = [entry for _, entry in dataset]
    # primeira entrada de cada par (índice par) é sempre a baseline
    baselines = entries[0::2]
    seguintes = entries[1::2]
    assert all(not e.is_anomalous for e in baselines)
    assert all(e.anomaly_type is None for e in baselines)
    assert all(e.anomaly_type == "mudanca_abrupta" for e in seguintes)  # abrupt_rate=1.0


def test_generate_sequence_dataset_determinismo_por_seed():
    a = generate_sequence_dataset(n_sequences=8, seed=5, abrupt_rate=0.4)
    b = generate_sequence_dataset(n_sequences=8, seed=5, abrupt_rate=0.4)
    labels_a = [(e.patient_id, e.dose, e.anomaly_type) for _, e in a]
    labels_b = [(e.patient_id, e.dose, e.anomaly_type) for _, e in b]
    assert labels_a == labels_b


def test_generate_dataset_to_disk_persiste_ground_truth_em_arquivo_separado(tmp_path):
    entries = generate_dataset_to_disk(n=5, seed=11, anomaly_rate=0.4, output_dir=tmp_path)

    ground_truth_path = tmp_path / "ground_truth.json"
    assert ground_truth_path.is_file()

    saved = json.loads(ground_truth_path.read_text())
    assert len(saved) == 5 == len(entries)

    for entry in entries:
        pdf_path = tmp_path / f"{entry.patient_id}.pdf"
        assert pdf_path.is_file()
        assert pdf_path.read_bytes()[:4] == b"%PDF"
        # o PDF em si nao contem o rotulo de anomalia -- só o arquivo de ground truth
        assert b"is_anomalous" not in pdf_path.read_bytes()

    saved_patient_ids = {item["patient_id"] for item in saved}
    assert saved_patient_ids == {e.patient_id for e in entries}
