from pipelines.prescription import catalog


def test_lookup_medicamento_conhecido():
    drug_range = catalog.lookup("paracetamol")
    assert drug_range is not None
    assert drug_range.drug == "paracetamol"
    assert drug_range.min_dose < drug_range.max_dose


def test_lookup_case_insensitive():
    assert catalog.lookup("Paracetamol") == catalog.lookup("paracetamol")


def test_lookup_medicamento_desconhecido_devolve_none():
    assert catalog.lookup("medicamento-inexistente-xyz") is None


def test_all_drugs_nao_vazio():
    drugs = catalog.all_drugs()
    assert len(drugs) >= 10
    assert "paracetamol" in drugs
