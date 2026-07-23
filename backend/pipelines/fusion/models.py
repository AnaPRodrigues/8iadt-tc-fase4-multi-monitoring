"""Dataclasses de domínio da fusão multimodal (F5), compartilhadas por todos os módulos
de `pipelines/fusion/` -- mesmo padrão de centralização de tipos usado em F1/F2
(`video/models.py`, `audio/models.py`).
"""

from dataclasses import dataclass

from common.evidence import Evidence


@dataclass(frozen=True)
class CuratedEventRef:
    modality: str  # "video" | "audio" | "vitals" | "prescription"
    feature: str  # nome da pasta em output/ (ex.: "video_pose", "audio", "vitals", "prescription")
    run_id: str
    evidence_id: str
    demo_timestamp_s: float  # curado manualmente (AD-045a) -- não derivado dos dados reais
    severity: float = 1.0  # override curado; default 1.0 (presença = anomalia já confirmada)


@dataclass(frozen=True)
class FusionEvent:
    modality: str
    demo_timestamp_s: float
    severity: float
    summary: str  # extraído do metadata real (ex.: "queda detectada", "crackle previsto")
    evidence: Evidence  # common.evidence.Evidence -- artifact_path/sidecar_path reais


@dataclass(frozen=True)
class RiskPoint:
    t: float
    score: float
    level: str  # "verde" | "amarelo" | "vermelho"
    contributions: dict[str, float]  # modalidade -> contribuição no score
    missing_modalities: list[str]  # modalidades sem nenhum evento até `t` (FUSION-04)
    contributing_events: list[FusionEvent]  # eventos que efetivamente pesaram neste ponto


@dataclass(frozen=True)
class Transition:
    t: float
    previous_level: str
    new_level: str
    point: RiskPoint


@dataclass(frozen=True)
class AlertPayload:
    patient_demo_id: str
    level: str
    dedup_key: str
    contributions: list[tuple[str, str, str]]  # (modalidade, resumo, link_s3_evidencia)
