"""Schemas Pydantic de entrada/saída da API.

Traduzem as entidades do banco local e o resultado do motor de fusão para o
formato HTTP consumido pela interface web.
"""

from pydantic import BaseModel


# --- Motor de fusão (linha do tempo de risco) ---
class FusionEventSchema(BaseModel):
    modality: str
    demo_timestamp_s: float
    severity: float
    summary: str
    evidence_id: str


class RiskPointSchema(BaseModel):
    t: float
    score: float
    level: str
    contributions: dict[str, float]
    missing_modalities: list[str]
    contributing_events: list[FusionEventSchema]


# --- Pacientes ---
class PacienteEntrada(BaseModel):
    nome: str
    data_inicio: str | None = None
    observacoes: str | None = None


class PacienteSchema(BaseModel):
    id: str
    nome: str
    data_inicio: str
    observacoes: str | None
    nivel_atual: str


# --- Uploads ---
class UploadSchema(BaseModel):
    id: str
    paciente_id: str
    modalidade: str
    nome_original: str
    criado_em: str
    situacao: str


# --- Análises ---
class AnaliseSchema(BaseModel):
    id: str
    upload_id: str
    modalidade: str
    resumo: str
    pontuacao: float | None
    evidencia_id: str | None
    criado_em: str
    detalhes: dict | None = None


# --- Alertas ---
class AlertaSchema(BaseModel):
    id: str
    paciente_id: str
    nivel: str
    pontuacao: float
    criado_em: str
    motivo: str
    referencias: list[str]
