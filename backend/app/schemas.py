"""Schemas Pydantic de resposta da API -- espelham os campos de
`pipelines.fusion.models` relevantes para o consumo HTTP pela interface web.
"""

from pydantic import BaseModel


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


class AlertSchema(BaseModel):
    """Uma transição de nível que cruzou o nível de disparo configurado -- é
    quando um alerta automático é gerado para a equipe. Cada contribuição é uma
    tripla (modalidade, resumo em linguagem clínica, link da evidência)."""

    t: float
    previous_level: str
    new_level: str
    contributions: list[tuple[str, str, str]]


class EvidenceSchema(BaseModel):
    evidence_id: str
    feature: str
    run_id: str
    source_record_id: str
    metadata: dict
