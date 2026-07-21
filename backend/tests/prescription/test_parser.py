from aws.adapters import ExtractedText
from pipelines.prescription.adapters import PdfplumberExtractor
from pipelines.prescription.generator import generate_prescription
from pipelines.prescription.models import ParseFailure, PrescriptionRecord
from pipelines.prescription.parser import parse_prescription


def test_parse_prescription_pdf_real_completo():
    pdf_bytes = generate_prescription(
        patient_id="p9", drug="paracetamol", dose=500, frequency="8/8h", seed=3
    )
    extracted = PdfplumberExtractor().extract(pdf_bytes)

    record = parse_prescription(extracted)

    assert isinstance(record, PrescriptionRecord)
    assert record.patient_id == "p9"
    assert record.drug == "paracetamol"
    assert record.dose == 500.0
    assert record.unit == "mg"
    assert record.frequency == "8/8h"


def test_parse_prescription_dose_ausente_e_parse_failure():
    extracted = ExtractedText(
        lines=["Paciente: p1", "Medicamento: paracetamol", "Frequência: 8/8h", "Data: 2026-01-01"],
        raw={},
    )
    result = parse_prescription(extracted)
    assert isinstance(result, ParseFailure)
    assert result.field == "Dose"


def test_parse_prescription_dose_nao_numerica_e_parse_failure():
    extracted = ExtractedText(
        lines=[
            "Paciente: p1",
            "Medicamento: paracetamol",
            "Dose: muita mg",
            "Frequência: 8/8h",
            "Data: 2026-01-01",
        ],
        raw={},
    )
    result = parse_prescription(extracted)
    assert isinstance(result, ParseFailure)
    assert result.field == "Dose"


def test_parse_prescription_frequencia_ausente_e_parse_failure():
    extracted = ExtractedText(
        lines=["Paciente: p1", "Medicamento: paracetamol", "Dose: 500 mg", "Data: 2026-01-01"],
        raw={},
    )
    result = parse_prescription(extracted)
    assert isinstance(result, ParseFailure)
    assert result.field == "Frequência"
