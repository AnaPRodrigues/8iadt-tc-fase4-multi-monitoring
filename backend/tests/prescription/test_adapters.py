from aws.adapters import get_text_extractor
from pipelines.prescription.adapters import PdfplumberExtractor, register_local_adapters
from pipelines.prescription.generator import generate_prescription


def test_pdfplumber_extractor_extrai_pdf_real_do_gerador():
    pdf_bytes = generate_prescription(
        patient_id="p42", drug="ibuprofeno", dose=400, frequency="8/8h", seed=5
    )
    extracted = PdfplumberExtractor().extract(pdf_bytes)

    assert any("p42" in line for line in extracted.lines)
    assert any("ibuprofeno" in line.lower() for line in extracted.lines)
    assert extracted.raw["page_count"] == 1


def test_register_local_adapters_resolve_via_get_text_extractor():
    register_local_adapters()
    extractor = get_text_extractor("local")
    assert isinstance(extractor, PdfplumberExtractor)


def test_extract_preserva_ordem_das_linhas():
    pdf_bytes = generate_prescription(
        patient_id="p1", drug="dipirona", dose=500, frequency="6/6h", seed=1
    )
    extracted = PdfplumberExtractor().extract(pdf_bytes)

    joined = " ".join(extracted.lines)
    assert joined.index("Paciente") < joined.index("Medicamento")
    assert joined.index("Medicamento") < joined.index("Dose")
