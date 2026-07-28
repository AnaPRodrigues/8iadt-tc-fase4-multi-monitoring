"""Catálogo curado de faixas terapêuticas e classificação regulatória ANVISA.

Faixas de dose diária usual em adultos a partir de bulas públicas da ANVISA
(Bulário Eletrônico). Categorias de controlo especial conforme Portaria
SVS/MS nº 344/98 e atualizações da ANVISA (RDC nº 373/2020, RDC nº 784/2023).

Valores aproximados para fins de demonstração académica; validar contra o
bulário oficial antes de qualquer uso clínico real.
"""

from pipelines.prescription.models import DrugRange

# Fonte padrão para medicamentos com informação verificada no Bulário Eletrónico.
_FONTE_ANVISA = "ANVISA — Bulário Eletrônico"
_FONTE_REFERENCIA = "ANVISA — Listas de Controlo Especial (Port. 344/98)"


def _d(name: str, min_dose: float, max_dose: float, unit: str = "mg",
       active: str = "", category: str = "", controlled: bool = False,
       source: str = "", criticality: int = 1) -> DrugRange:
    """Factory concisa para entradas do catálogo.

    ``criticality``: 1 = Baixo Risco/Uso Geral, 2 = Médio Risco,
    3 = Alto Risco / Medicamentos de Alta Vigilância (MAV/ISMP).
    """
    return DrugRange(
        name=name, min_dose=min_dose, max_dose=max_dose, unit=unit,
        active_ingredient=active, control_category=category,
        is_controlled=controlled,
        source=source or (_FONTE_ANVISA if not controlled else _FONTE_REFERENCIA),
        criticality=criticality,
    )


# --------------------------------------------------------------------------- #
# Catálogo — 24 fármacos com dados reais ANVISA
# --------------------------------------------------------------------------- #
_CATALOG: dict[str, DrugRange] = {
    entry.name.lower(): entry
    for entry in [

        # ---- Não controlados (criticality=1: Baixo Risco) ----
        _d("paracetamol", 500, 1000, active="paracetamol",
           source=_FONTE_ANVISA, criticality=1),
        _d("ibuprofeno", 200, 800, active="ibuprofeno",
           source=_FONTE_ANVISA, criticality=1),
        _d("dipirona", 500, 1000, active="dipirona sódica",
           source=_FONTE_ANVISA, criticality=1),
        _d("amoxicilina", 250, 875, active="amoxicilina",
           source=_FONTE_ANVISA, criticality=1),
        _d("losartana", 25, 100, active="losartana potássica",
           source=_FONTE_ANVISA, criticality=1),
        _d("metformina", 500, 2000, active="cloridrato de metformina",
           source=_FONTE_ANVISA, criticality=1),
        _d("omeprazol", 20, 40, active="omeprazol",
           source=_FONTE_ANVISA, criticality=1),
        _d("enalapril", 5, 40, active="maleato de enalapril",
           source=_FONTE_ANVISA, criticality=1),
        _d("sinvastatina", 10, 80, active="sinvastatina",
           source=_FONTE_ANVISA, criticality=1),
        _d("furosemida", 20, 80, active="furosemida",
           source=_FONTE_ANVISA, criticality=1),
        _d("prednisona", 5, 60, active="prednisona",
           source=_FONTE_ANVISA, criticality=1),
        _d("azitromicina", 250, 500, active="azitromicina",
           source=_FONTE_ANVISA, criticality=1),
        _d("cetoprofeno", 50, 200, active="cetoprofeno",
           source=_FONTE_ANVISA, criticality=1),

        # ---- Médio Risco (criticality=2): controlados não-entorpecentes, MAV não-opioides ----
        _d("varfarina", 1, 10, active="varfarina sódica",
           source=_FONTE_ANVISA, criticality=2),
        _d("insulina", 1, 100, unit="UI", active="insulina humana",
           source=_FONTE_ANVISA, criticality=2),
        _d("digoxina", 0.125, 0.5, active="digoxina",
           source=_FONTE_ANVISA, criticality=2),

        # ---- A1 — Entorpecentes (criticality=3: Alto Risco / MAV) ----
        _d("morfina", 10, 60, active="sulfato de morfina",
           category="A1", controlled=True, criticality=3),
        _d("fentanil", 0.012, 0.100, unit="mg/h", active="citrato de fentanila",
           category="A1", controlled=True, criticality=3),
        _d("metadona", 5, 40, active="cloridrato de metadona",
           category="A1", controlled=True, criticality=3),

        # ---- A2 — Entorpecentes (criticality=2: Médio Risco) ----
        _d("codeína", 30, 120, active="fosfato de codeína",
           category="A2", controlled=True, criticality=2),
        _d("tramadol", 50, 400, active="cloridrato de tramadol",
           category="A2", controlled=True, criticality=2),

        # ---- B1 — Psicotrópicos (criticality=2: Médio Risco) ----
        _d("diazepam", 5, 20, active="diazepam",
           category="B1", controlled=True, criticality=2),
        _d("clonazepam", 0.5, 4, active="clonazepam",
           category="B1", controlled=True, criticality=2),
        _d("alprazolam", 0.5, 4, active="alprazolam",
           category="B1", controlled=True, criticality=2),
        _d("midazolam", 7.5, 15, active="midazolam",
           category="B1", controlled=True, criticality=2),
        _d("metilfenidato", 10, 60, active="cloridrato de metilfenidato",
           category="B1", controlled=True, criticality=2),

        # ---- C1 — Controlo Especial (criticality=2: Médio Risco) ----
        _d("fluoxetina", 20, 60, active="cloridrato de fluoxetina",
           category="C1", controlled=True, criticality=2),
        _d("sertralina", 50, 200, active="cloridrato de sertralina",
           category="C1", controlled=True, criticality=2),
        _d("carbamazepina", 200, 1200, active="carbamazepina",
           category="C1", controlled=True, criticality=2),
        _d("haloperidol", 1, 15, active="haloperidol",
           category="C1", controlled=True, criticality=2),
        _d("risperidona", 1, 6, active="risperidona",
           category="C1", controlled=True, criticality=2),
    ]
}


def lookup(drug: str) -> DrugRange | None:
    """Devolve a faixa terapêutica + classificação regulatória do medicamento
    (case-insensitive) ou ``None`` se estiver fora do catálogo."""
    return _CATALOG.get(drug.lower())


def all_drugs() -> list[str]:
    """Lista os medicamentos cadastrados no catálogo."""
    return sorted(_CATALOG.keys())


def controlled_substances() -> list[str]:
    """Lista apenas os medicamentos sujeitos a controlo especial."""
    return sorted(
        name for name, entry in _CATALOG.items() if entry.is_controlled
    )
