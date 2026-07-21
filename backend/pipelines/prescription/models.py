"""Dataclasses centrais do pipeline de prescrições (F4)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DrugRange:
    """Faixa terapêutica de referência para um medicamento."""

    drug: str
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
    detail: str


@dataclass(frozen=True)
class GroundTruthEntry:
    """Rótulo esperado de um PDF sintético gerado por ``generator.py``."""

    record: PrescriptionRecord
    expected_kind: str


@dataclass(frozen=True)
class ProcessResult:
    """Resultado do processamento de ponta a ponta de um evento S3."""

    record: PrescriptionRecord | None
    anomalies: list[AnomalyResult]
    deduplicated: bool
    parse_failure: ParseFailure | None
