"""Monta o payload explicável do alerta e a chave de dedupe determinística
(FUSION-07, FUSION-08).
"""

from pipelines.fusion.models import AlertPayload, RiskPoint


def dedup_key(point: RiskPoint) -> str:
    """Chave determinística a partir dos `evidence_id` dos eventos contribuintes --
    não do timestamp da chamada -- para que reenviar o mesmo conjunto de eventos
    sempre gere a mesma chave (dedupe por evento de origem, FUSION-08).

    Ordenada para que a chave dependa só do CONJUNTO de eventos contribuintes,
    nunca da ordem em que `contributing_events` aparece no `RiskPoint`.
    """
    evidence_ids = sorted(event.evidence.evidence_id for event in point.contributing_events)
    return "|".join(evidence_ids)


def build_payload(point: RiskPoint, patient_demo_id: str) -> AlertPayload:
    """Monta o payload explicável: ID do paciente-demo, nível e, para cada evento
    contribuinte, `(modalidade, resumo, link da evidência)` (FUSION-07).

    SPEC_DEVIATION: a spec descreve "links das evidências no S3", mas o
    paciente-demo nunca faz upload de evidência ao S3 -- `loader.py` lê sidecars
    reais já gravados localmente em `output/<feature>/<run_id>/` (AD-045). O link
    aqui aponta para o endpoint `/evidence/{id}` da própria API de F5 (FUSION-12),
    que de fato serve o artefato -- fabricar uma URL `s3://` que não aponta para
    nada seria menos honesto que reusar o mecanismo real de drill-down do sistema.
    """
    contributions = [
        (event.modality, event.summary, f"/evidence/{event.evidence.evidence_id}")
        for event in point.contributing_events
    ]
    return AlertPayload(
        patient_demo_id=patient_demo_id,
        level=point.level,
        dedup_key=dedup_key(point),
        contributions=contributions,
    )
