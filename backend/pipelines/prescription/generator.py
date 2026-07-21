"""Gerador de prescrições sintéticas com ground truth conhecido (PRESC-01).

Os PDFs contêm texto real embutido via ``reportlab`` (não uma imagem escaneada),
o que permite extração direta por ``pdfplumber`` sem OCR — verificado em REPL
durante o design (round-trip preserva a ordem das linhas).

SPEC_DEVIATION: o design descreve ``generate_dataset(n, seed, anomaly_rate) ->
list[GroundTruthEntry]``. Aqui o retorno inclui também os bytes do PDF —
``list[tuple[bytes, GroundTruthEntry]]`` — porque sem o PDF em mãos os testes
(e a integração de T7) não teriam como associar o rótulo esperado ao artefato
real; `generate_dataset` não tem responsabilidade de subir para o S3 (isso é do
chamador/teste).

``generate_dataset`` produz apenas o rótulo ``"dose_fora_de_faixa"`` (PRESC-01,
P1). "Mudança abrupta" depende de uma sequência de dois registros do mesmo
paciente/medicamento — é exercida diretamente pelos testes de integração de
T6, chamando ``generate_prescription`` duas vezes, não por um rótulo isolado
aqui.
"""

import io
import random
from datetime import datetime, timedelta

from reportlab.pdfgen import canvas

from pipelines.prescription import catalog
from pipelines.prescription.models import GroundTruthEntry

_BASE_TIMESTAMP = datetime(2026, 1, 1)
_DEFAULT_UNIT = "mg"


def _timestamp_from_seed(seed: int) -> str:
    """Timestamp ISO-8601 determinístico a partir do seed (segundos após a base)."""
    return (_BASE_TIMESTAMP + timedelta(seconds=seed)).isoformat()


def generate_prescription(
    patient_id: str, drug: str, dose: float, frequency: str, seed: int
) -> bytes:
    """Gera um PDF de prescrição com texto real embutido."""
    drug_range = catalog.lookup(drug)
    unit = drug_range.unit if drug_range is not None else _DEFAULT_UNIT
    timestamp = _timestamp_from_seed(seed)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    lines = [
        f"Paciente: {patient_id}",
        f"Medicamento: {drug}",
        f"Dose: {dose} {unit}",
        f"Frequência: {frequency}",
        f"Data: {timestamp}",
    ]
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def generate_dataset(
    n: int, seed: int, anomaly_rate: float = 0.3
) -> list[tuple[bytes, GroundTruthEntry]]:
    """Gera ``n`` prescrições sintéticas com proporção conhecida de anomalias."""
    rng = random.Random(seed)
    drugs = catalog.all_drugs()
    dataset: list[tuple[bytes, GroundTruthEntry]] = []

    for i in range(n):
        drug = rng.choice(drugs)
        drug_range = catalog.lookup(drug)
        assert drug_range is not None  # vem do catálogo, sempre resolve

        is_anomalous = rng.random() < anomaly_rate
        if is_anomalous:
            dose = (
                drug_range.min_dose * rng.uniform(0.1, 0.5)
                if rng.random() < 0.5
                else drug_range.max_dose * rng.uniform(1.5, 3.0)
            )
            anomaly_type = "dose_fora_de_faixa"
        else:
            dose = rng.uniform(drug_range.min_dose, drug_range.max_dose)
            anomaly_type = None

        patient_id = f"patient-{seed}-{i:04d}"
        pdf_bytes = generate_prescription(
            patient_id=patient_id,
            drug=drug,
            dose=round(dose, 2),
            frequency="8/8h",
            seed=seed + i,
        )
        dataset.append(
            (
                pdf_bytes,
                GroundTruthEntry(
                    patient_id=patient_id,
                    drug=drug,
                    dose=round(dose, 2),
                    is_anomalous=is_anomalous,
                    anomaly_type=anomaly_type,
                ),
            )
        )

    return dataset
