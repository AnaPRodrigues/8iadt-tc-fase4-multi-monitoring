"""Monta o alerta explicável e a chave determinística que identifica o conjunto
de eventos que o originou (para evitar alertas duplicados do mesmo conjunto).
"""

from pipelines.fusion.models import AlertPayload, RiskPoint


def dedup_key(point: RiskPoint) -> str:
    """Chave determinística a partir dos identificadores das evidências que
    contribuíram -- não do horário da chamada -- para que o mesmo conjunto de
    eventos sempre gere a mesma chave, evitando alertas duplicados.

    Ordenada para que a chave dependa só do CONJUNTO de eventos contribuintes,
    nunca da ordem em que aparecem no ponto de risco.
    """
    evidence_ids = sorted(event.evidence.evidence_id for event in point.contributing_events)
    return "|".join(evidence_ids)


def build_payload(point: RiskPoint, patient_demo_id: str) -> AlertPayload:
    """Monta o alerta explicável: identificação do paciente, nível e, para cada
    evento contribuinte, `(modalidade, resumo, link da evidência)`.

    O link aponta para o endpoint `/evidence/{id}` da própria API, que serve o
    artefato real (imagem/gráfico/documento) gravado localmente pela análise de
    origem -- é assim que a interface abre o detalhe de cada evento.
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
