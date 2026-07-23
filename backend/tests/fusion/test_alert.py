"""Testes de `pipelines.fusion.alert` -- payload explicável de alerta e chave de
dedupe determinística (FUSION-07, FUSION-08)."""

from pathlib import Path

from common.evidence import Evidence
from pipelines.fusion.alert import build_payload, dedup_key
from pipelines.fusion.models import FusionEvent, RiskPoint


def _evento(modality: str, evidence_id: str, summary: str = "evento") -> FusionEvent:
    return FusionEvent(
        modality=modality,
        demo_timestamp_s=10.0,
        severity=1.0,
        summary=summary,
        evidence=Evidence(
            feature=modality,
            run_id="run-teste",
            evidence_id=evidence_id,
            source_record_id="rec-1",
            artifact_path=Path(f"output/{modality}/run-teste/{evidence_id}.png"),
            sidecar_path=Path(f"output/{modality}/run-teste/{evidence_id}.json"),
        ),
    )


def _ponto(t: float, level: str, contributing_events: list[FusionEvent]) -> RiskPoint:
    return RiskPoint(
        t=t,
        score=0.8,
        level=level,
        contributions={e.modality: 0.5 for e in contributing_events},
        missing_modalities=[],
        contributing_events=contributing_events,
    )


# ---------- dedup_key ----------


def test_dedup_key_e_deterministico_a_partir_dos_evidence_ids_nao_do_timestamp():
    eventos = [_evento("video", "fall-01"), _evento("vitals", "hr-anomaly-02")]
    ponto_t60 = _ponto(t=60.0, level="vermelho", contributing_events=eventos)
    ponto_t120 = _ponto(t=120.0, level="vermelho", contributing_events=eventos)

    # mesmo conjunto de eventos contribuintes, timestamps do RiskPoint diferentes
    # -- a chave não pode variar com o `t` da chamada.
    assert dedup_key(ponto_t60) == dedup_key(ponto_t120)


def test_dedup_key_mesmo_conjunto_em_ordem_diferente_gera_a_mesma_chave():
    a = _evento("video", "fall-01")
    b = _evento("vitals", "hr-anomaly-02")
    ponto_ordem_1 = _ponto(t=10.0, level="vermelho", contributing_events=[a, b])
    ponto_ordem_2 = _ponto(t=10.0, level="vermelho", contributing_events=[b, a])

    assert dedup_key(ponto_ordem_1) == dedup_key(ponto_ordem_2)


def test_dedup_key_conjuntos_diferentes_geram_chaves_diferentes():
    ponto_a = _ponto(t=10.0, level="vermelho", contributing_events=[_evento("video", "fall-01")])
    ponto_b = _ponto(
        t=10.0, level="vermelho", contributing_events=[_evento("video", "fall-02")]
    )

    assert dedup_key(ponto_a) != dedup_key(ponto_b)


# ---------- build_payload ----------


def test_build_payload_monta_id_nivel_e_contribuicoes_a_partir_dos_eventos():
    eventos = [
        _evento("video", "fall-01", summary="queda detectada"),
        _evento("vitals", "hr-anomaly-02", summary="taquicardia"),
    ]
    ponto = _ponto(t=60.0, level="vermelho", contributing_events=eventos)

    payload = build_payload(ponto, patient_demo_id="demo-1")

    assert payload.patient_demo_id == "demo-1"
    assert payload.level == "vermelho"
    assert payload.contributions == [
        ("video", "queda detectada", "/evidence/fall-01"),
        ("vitals", "taquicardia", "/evidence/hr-anomaly-02"),
    ]


def test_build_payload_usa_dedup_key_do_conjunto_de_eventos_contribuintes():
    eventos = [_evento("video", "fall-01")]
    ponto = _ponto(t=60.0, level="vermelho", contributing_events=eventos)

    payload = build_payload(ponto, patient_demo_id="demo-1")

    assert payload.dedup_key == dedup_key(ponto)


def test_build_payload_sem_eventos_contribuintes_gera_lista_vazia():
    ponto = _ponto(t=0.0, level="verde", contributing_events=[])

    payload = build_payload(ponto, patient_demo_id="demo-1")

    assert payload.contributions == []
