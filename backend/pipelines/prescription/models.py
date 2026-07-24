"""Dataclasses centrais do pipeline de prescrições."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DrugRange:
    """Faixa terapêutica de referência para um medicamento."""

    name: str
    min_dose: float
    max_dose: float
    unit: str


@dataclass(frozen=True)
class PrescriptionRecord:
    """Registro estruturado extraído de uma prescrição."""

    patient_id: str
    drug: str
    dose: float
    unit: str
    frequency: str
    timestamp: str


@dataclass(frozen=True)
class ParseFailure:
    """Sinaliza que um campo obrigatório não pôde ser extraído da prescrição."""

    reason: str
    field: str


@dataclass(frozen=True)
class AnomalyResult:
    """Resultado de uma regra de anomalia aplicada a um ``PrescriptionRecord``."""

    kind: str
    reason: str


@dataclass(frozen=True)
class GroundTruthEntry:
    """Rótulo esperado de um PDF sintético gerado por ``generator.py``.

    ``timestamp`` existe para que ``evaluate.py`` consiga casar cada rótulo com o
    registro exato (patient_id+drug sozinhos colidem em sequências de mudança
    abrupta, onde o mesmo paciente/medicamento aparece mais de uma vez) e
    reconstruir a ordem para a regra de mudança abrupta.
    """

    patient_id: str
    drug: str
    dose: float
    is_anomalous: bool
    anomaly_type: str | None
    timestamp: str


@dataclass(frozen=True)
class ProcessResult:
    """Resultado do processamento de ponta a ponta de uma prescrição.

    ``parse_failure`` existe para distinguir "PDF ilegível" de "parseado, sem
    anomalias".
    """

    record: PrescriptionRecord | None
    anomalies: list[AnomalyResult]
    evidence_id: str | None
    parse_failure: ParseFailure | None = None
