from pipelines.prescription import catalog


def test_lookup_medicamento_conhecido():
    drug_range = catalog.lookup("paracetamol")
    assert drug_range is not None
    assert drug_range.name == "paracetamol"
    assert drug_range.min_dose < drug_range.max_dose


def test_lookup_case_insensitive():
    assert catalog.lookup("Paracetamol") == catalog.lookup("paracetamol")


def test_lookup_medicamento_desconhecido_devolve_none():
    assert catalog.lookup("medicamento-inexistente-xyz") is None


def test_all_drugs_nao_vazio():
    drugs = catalog.all_drugs()
    assert len(drugs) >= 10
    assert "paracetamol" in drugs


# --- Catálogo ANVISA ---

def test_medicamento_controlado_a1_tem_categoria():
    """morfina é A1 — entorpecente com notificação de receita A."""
    entry = catalog.lookup("morfina")
    assert entry is not None
    assert entry.control_category == "A1"
    assert entry.is_controlled is True
    assert entry.active_ingredient == "sulfato de morfina"


def test_medicamento_controlado_b1_tem_categoria():
    """diazepam é B1 — psicotrópico com notificação de receita B."""
    entry = catalog.lookup("diazepam")
    assert entry is not None
    assert entry.control_category == "B1"
    assert entry.is_controlled is True


def test_medicamento_c1_tem_categoria():
    """fluoxetina é C1 — controlo especial com receita C."""
    entry = catalog.lookup("fluoxetina")
    assert entry is not None
    assert entry.control_category == "C1"
    assert entry.is_controlled is True


def test_medicamento_nao_controlado():
    """paracetamol não é controlado."""
    entry = catalog.lookup("paracetamol")
    assert entry is not None
    assert entry.is_controlled is False
    assert entry.control_category == ""


def test_medicamento_tem_principio_ativo():
    """cada medicamento tem princípio ativo (DCB)."""
    entry = catalog.lookup("losartana")
    assert entry is not None
    assert "losartana" in entry.active_ingredient.lower()


def test_medicamento_controlado_tem_fonte():
    """medicamentos controlados referenciam a fonte ANVISA."""
    entry = catalog.lookup("codeína")
    assert entry is not None
    assert "ANVISA" in entry.source


def test_medicamento_nao_controlado_tem_fonte():
    """mesmo não controlados têm fonte documentada."""
    entry = catalog.lookup("amoxicilina")
    assert entry is not None
    assert "ANVISA" in entry.source or "não verificado" in entry.source.lower()


def test_controlled_substances_lista_apenas_controlados():
    """controlled_substances() não inclui não-controlados."""
    controlled = catalog.controlled_substances()
    assert "morfina" in controlled
    assert "paracetamol" not in controlled
    assert len(controlled) >= 5  # pelo menos A1, A2, B1, C1 têm exemplos


def test_catalogo_tem_24_ou_mais_farmacos():
    """O catálogo expandido cobre as 4 listas ANVISA + não controlados."""
    assert len(catalog.all_drugs()) >= 24


# --- DrugRange.criticality ---

def test_medicamento_risco_baixo_tem_criticality_1():
    """dipirona e paracetamol são risco baixo (criticality=1)."""
    for nome in ("dipirona", "paracetamol", "ibuprofeno", "amoxicilina"):
        entry = catalog.lookup(nome)
        assert entry is not None, f"{nome} ausente do catálogo"
        assert entry.criticality == 1, f"{nome} devia ser criticality=1, é {entry.criticality}"


def test_medicamento_risco_medio_tem_criticality_2():
    """tramadol e codeína são risco médio (criticality=2)."""
    for nome in ("tramadol", "codeína"):
        entry = catalog.lookup(nome)
        assert entry is not None, f"{nome} ausente do catálogo"
        assert entry.criticality == 2, f"{nome} devia ser criticality=2, é {entry.criticality}"


def test_medicamento_alta_vigilancia_tem_criticality_3():
    """morfina, fentanil, metadona são MAV (criticality=3)."""
    for nome in ("morfina", "fentanil", "metadona"):
        entry = catalog.lookup(nome)
        assert entry is not None, f"{nome} ausente do catálogo"
        assert entry.criticality == 3, f"{nome} devia ser criticality=3, é {entry.criticality}"


def test_lookup_medicamento_desconhecido_retorna_none_sem_fallback():
    """lookup de fármaco inexistente retorna None (sem_referencia)."""
    assert catalog.lookup("medicamento-inventado-xyz") is None
