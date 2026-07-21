"""Estrutura um `PrescriptionRecord` a partir do texto extraído do PDF (PRESC-04).

Campo ausente ou dose não numérica vira `ParseFailure` explícito, nomeando o
campo — nunca um valor inferido/adivinhado.
"""

from aws.adapters import ExtractedText
from pipelines.prescription.models import ParseFailure, PrescriptionRecord

_REQUIRED_LABELS = {
    "Paciente": "patient_id",
    "Medicamento": "drug",
    "Dose": "dose",
    "Frequência": "frequency",
    "Data": "timestamp",
}


def parse_prescription(extracted: ExtractedText) -> PrescriptionRecord | ParseFailure:
    """Estrutura os campos da prescrição a partir das linhas extraídas do PDF."""
    fields: dict[str, str] = {}
    for line in extracted.lines:
        if ": " not in line:
            continue
        label, _, value = line.partition(": ")
        fields[label.strip()] = value.strip()

    for label in _REQUIRED_LABELS:
        if label not in fields or not fields[label]:
            return ParseFailure(reason="campo ausente na extração", field=label)

    dose_raw = fields["Dose"]
    dose_parts = dose_raw.split(" ", 1)
    dose_value = dose_parts[0]
    unit = dose_parts[1] if len(dose_parts) > 1 else ""

    try:
        dose = float(dose_value)
    except ValueError:
        return ParseFailure(reason=f"dose não numérica: {dose_value!r}", field="Dose")

    return PrescriptionRecord(
        patient_id=fields["Paciente"],
        drug=fields["Medicamento"],
        dose=dose,
        unit=unit,
        frequency=fields["Frequência"],
        timestamp=fields["Data"],
    )
