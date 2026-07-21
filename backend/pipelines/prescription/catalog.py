"""Catálogo curado de faixas terapêuticas por medicamento (PRESC-05).

Faixas de dose diária usual em adultos, a partir de bulas públicas — valores
aproximados para fins de demonstração; validar contra bulário oficial antes de
qualquer uso além do relatório técnico deste projeto.
"""

from pipelines.prescription.models import DrugRange

_CATALOG: dict[str, DrugRange] = {
    entry.drug.lower(): entry
    for entry in [
        DrugRange(drug="paracetamol", min_dose=500, max_dose=1000, unit="mg"),
        DrugRange(drug="ibuprofeno", min_dose=200, max_dose=800, unit="mg"),
        DrugRange(drug="amoxicilina", min_dose=250, max_dose=875, unit="mg"),
        DrugRange(drug="dipirona", min_dose=500, max_dose=1000, unit="mg"),
        DrugRange(drug="losartana", min_dose=25, max_dose=100, unit="mg"),
        DrugRange(drug="metformina", min_dose=500, max_dose=2000, unit="mg"),
        DrugRange(drug="omeprazol", min_dose=20, max_dose=40, unit="mg"),
        DrugRange(drug="enalapril", min_dose=5, max_dose=40, unit="mg"),
        DrugRange(drug="sinvastatina", min_dose=10, max_dose=80, unit="mg"),
        DrugRange(drug="varfarina", min_dose=1, max_dose=10, unit="mg"),
        DrugRange(drug="insulina", min_dose=1, max_dose=100, unit="UI"),
        DrugRange(drug="digoxina", min_dose=0.125, max_dose=0.5, unit="mg"),
        DrugRange(drug="furosemida", min_dose=20, max_dose=80, unit="mg"),
        DrugRange(drug="prednisona", min_dose=5, max_dose=60, unit="mg"),
    ]
}


def lookup(drug: str) -> DrugRange | None:
    """Devolve a faixa terapêutica do medicamento (case-insensitive) ou ``None``."""
    return _CATALOG.get(drug.lower())


def all_drugs() -> list[str]:
    """Lista os medicamentos cadastrados no catálogo."""
    return [entry.drug for entry in _CATALOG.values()]
