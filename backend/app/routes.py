"""Rotas HTTP da API fina de F5 (AD-044/AD-029) -- expõe o motor de fusão
(`pipelines/fusion/`) para o dashboard Streamlit.

Importa `app` de `main.py` e decora as rotas diretamente nele (sem `APIRouter`
-- só 4 rotas ao todo, não justifica a camada extra). Este módulo precisa ser
importado (ex.: `from app import routes`) para que as rotas sejam de fato
registradas no `app` compartilhado -- `main.py` só instancia o app, não importa
`routes.py` de volta (evita import circular).
"""

import json
import mimetypes
import os
from dataclasses import replace
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.main import app
from app.schemas import AlertSchema, FusionEventSchema, RiskPointSchema
from aws.clients import get_client
from common.logging import get_logger
from pipelines.fusion.alert import build_payload
from pipelines.fusion.config import PatientDemoConfig, load_patient_demo_config
from pipelines.fusion.hysteresis import VERDE, HysteresisClassifier
from pipelines.fusion.loader import load_events
from pipelines.fusion.models import FusionEvent, RiskPoint, Transition
from pipelines.fusion.risk_engine import compute_timeline
from pipelines.fusion.transitions import record_transition

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


def _alert_transitions(points: list[RiskPoint], alert_level: str) -> list[Transition]:
    """Deriva as `Transition` a partir da timeline já classificada (nível muda
    entre pontos consecutivos), filtrando só as que atingem `alert_level` -- são
    essas que efetivamente disparam um alerta SNS (FUSION-07)."""
    transitions: list[Transition] = []
    previous_level = VERDE  # mesmo nível inicial de HysteresisClassifier
    for point in points:
        if point.level != previous_level:
            transitions.append(record_transition(previous_level, point.level, point))
        previous_level = point.level
    return [t for t in transitions if t.new_level == alert_level]


def _is_confirmed(dedup_key: str) -> bool:
    """Verifica no DynamoDB se o alerta de `dedup_key` foi de fato confirmado como
    enviado -- `handler.py` só grava `ALERT#<dedup_key>` quando o SNS publica com
    sucesso (FUSION-09), então a presença do item É a confirmação. Sem
    `DYNAMODB_TABLE` configurada (API rodando sem infra de alerta de pé), o
    alerta é reportado como não confirmado em vez de derrubar a rota."""
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return False
    client = get_client("dynamodb")
    response = client.get_item(
        TableName=table_name, Key={"pk": {"S": f"ALERT#{dedup_key}"}, "sk": {"S": "ALERT"}}
    )
    return "Item" in response


def _to_alert_schema(patient_demo_id: str, transition: Transition) -> AlertSchema:
    payload = build_payload(transition.point, patient_demo_id)
    return AlertSchema(
        t=transition.t,
        previous_level=transition.previous_level,
        new_level=transition.new_level,
        dedup_key=payload.dedup_key,
        contributions=payload.contributions,
        confirmed=_is_confirmed(payload.dedup_key),
    )


@app.get("/alerts", response_model=list[AlertSchema])
def get_alerts(patient_demo_id: str) -> list[AlertSchema]:
    """Transições que cruzaram o nível de disparo configurado (`alert_level`),
    com o status de confirmação de envio do alerta (FUSION-09)."""
    cfg = _load_config_or_404(patient_demo_id)
    points = _classified_timeline(cfg)
    transitions = _alert_transitions(points, cfg.alert_level)
    return [_to_alert_schema(patient_demo_id, t) for t in transitions]


def _find_evidence_sidecar(evidence_id: str) -> Path | None:
    """Busca `<evidence_id>.json` em qualquer `output/<feature>/<run_id>/` -- a
    rota só recebe o `evidence_id` (sem feature/run_id, mesmo contrato do design),
    então a busca é por nome de arquivo em toda a árvore de evidências."""
    if not _OUTPUT_ROOT.is_dir():
        return None
    for sidecar in sorted(_OUTPUT_ROOT.glob(f"*/*/{evidence_id}.json")):
        return sidecar
    return None


@app.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str) -> FileResponse:
    """Serve o artefato real da evidência (imagem/texto/etc., pelo `content-type`
    inferido da extensão) com os metadados do sidecar embutidos como headers --
    é o proxy fino sobre `common/evidence.py` que resolve o drill-down por
    evento (FUSION-12)."""
    sidecar_path = _find_evidence_sidecar(evidence_id)
    if sidecar_path is None:
        raise HTTPException(status_code=404, detail=f"evidência inexistente: {evidence_id}")

    raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    artifact_path = sidecar_path.parent / raw["artifact"]
    media_type, _ = mimetypes.guess_type(str(artifact_path))
    return FileResponse(
        path=artifact_path,
        media_type=media_type or "application/octet-stream",
        headers={
            "X-Evidence-Feature": raw["feature"],
            "X-Evidence-Run-Id": raw["run_id"],
            "X-Evidence-Source-Record-Id": raw["source_record_id"],
        },
    )
