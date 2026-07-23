"""Rotas HTTP da API fina de F5 (AD-044/AD-029) -- expõe o motor de fusão
(`pipelines/fusion/`) para o dashboard Streamlit.

Importa `app` de `main.py` e decora as rotas diretamente nele (sem `APIRouter`
-- só 4 rotas ao todo, não justifica a camada extra). Este módulo precisa ser
importado (ex.: `from app import routes`) para que as rotas sejam de fato
registradas no `app` compartilhado -- `main.py` só instancia o app, não importa
`routes.py` de volta (evita import circular).
"""

from dataclasses import replace
from pathlib import Path

from fastapi import HTTPException

from app.main import app
from app.schemas import FusionEventSchema, RiskPointSchema
from common.logging import get_logger
from pipelines.fusion.config import PatientDemoConfig, load_patient_demo_config
from pipelines.fusion.hysteresis import HysteresisClassifier
from pipelines.fusion.loader import load_events
from pipelines.fusion.models import FusionEvent, RiskPoint
from pipelines.fusion.risk_engine import compute_timeline

log = get_logger("app.routes")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIGS_DIR = _REPO_ROOT / "backend" / "pipelines" / "fusion" / "configs"
_OUTPUT_ROOT = _REPO_ROOT / "output"


def _load_config_or_404(patient_demo_id: str) -> PatientDemoConfig:
    config_path = _CONFIGS_DIR / f"{patient_demo_id}.yaml"
    if not config_path.is_file():
        raise HTTPException(
            status_code=404, detail=f"paciente-demo inexistente: {patient_demo_id}"
        )
    return load_patient_demo_config(config_path)


def _to_event_schema(event: FusionEvent) -> FusionEventSchema:
    return FusionEventSchema(
        modality=event.modality,
        demo_timestamp_s=event.demo_timestamp_s,
        severity=event.severity,
        summary=event.summary,
        evidence_id=event.evidence.evidence_id,
    )


def _to_point_schema(point: RiskPoint) -> RiskPointSchema:
    return RiskPointSchema(
        t=point.t,
        score=point.score,
        level=point.level,
        contributions=point.contributions,
        missing_modalities=point.missing_modalities,
        contributing_events=[_to_event_schema(e) for e in point.contributing_events],
    )


def _classified_timeline(cfg: PatientDemoConfig) -> list[RiskPoint]:
    """Roda loader+risk_engine+hysteresis de ponta a ponta.

    `RiskPoint.level` bruto do `risk_engine` sai `""` -- a classificação com
    memória de estado entre janelas é responsabilidade exclusiva do
    `HysteresisClassifier` (ver docstring de `pipelines/fusion/risk_engine.py`),
    aplicado aqui em sequência sobre a timeline ordenada.
    """
    events, failures = load_events(cfg, _OUTPUT_ROOT)
    for failure in failures:
        log.warning("referência de evidência não resolvida: %s", failure)

    points = compute_timeline(events, cfg)
    classifier = HysteresisClassifier(cfg.threshold_amarelo, cfg.threshold_vermelho, cfg.hysteresis)
    return [replace(point, level=classifier.update(point.score)) for point in points]


@app.get("/patients/{patient_demo_id}/timeline", response_model=list[RiskPointSchema])
def get_timeline(patient_demo_id: str) -> list[RiskPointSchema]:
    """Timeline completa do paciente-demo: um `RiskPoint` classificado por janela."""
    cfg = _load_config_or_404(patient_demo_id)
    return [_to_point_schema(point) for point in _classified_timeline(cfg)]


@app.get("/analyze", response_model=RiskPointSchema)
def analyze(patient_demo_id: str) -> RiskPointSchema:
    """Estado atual do paciente-demo -- nível, score e modalidades ausentes do
    ponto mais recente da timeline (mesmo motor de `/patients/{id}/timeline`)."""
    cfg = _load_config_or_404(patient_demo_id)
    timeline = _classified_timeline(cfg)
    if not timeline:
        raise HTTPException(
            status_code=404, detail=f"paciente-demo sem eventos resolvidos: {patient_demo_id}"
        )
    return _to_point_schema(timeline[-1])
