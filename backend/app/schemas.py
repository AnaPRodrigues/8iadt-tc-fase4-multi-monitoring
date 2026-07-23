"""Schemas Pydantic de resposta da API fina de F5 (AD-044) -- espelham os campos
de `pipelines.fusion.models` relevantes para o consumo HTTP (dashboard Streamlit).
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
    """Uma transição de nível que cruzou o `alert_level` configurado, com o status
    de confirmação de envio (FUSION-09) -- `confirmed` reflete se o dedupe do
    alerta foi de fato gravado no DynamoDB (só acontece quando o SNS publica com
    sucesso, ver `pipelines/fusion/handler.py`)."""

    t: float
    previous_level: str
    new_level: str
    dedup_key: str
    contributions: list[tuple[str, str, str]]
    confirmed: bool


class EvidenceSchema(BaseModel):
    evidence_id: str
    feature: str
    run_id: str
    source_record_id: str
    metadata: dict
