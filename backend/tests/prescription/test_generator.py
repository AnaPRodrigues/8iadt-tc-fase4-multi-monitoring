import io

import pdfplumber

from pipelines.prescription.generator import generate_dataset, generate_prescription


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
