"""Testes de `pipelines.fusion.loader.load_events` -- resolução de eventos curados em
evidência real de F1-F4 (FUSION-01)."""

from pathlib import Path

import pytest

from pipelines.fusion.config import PatientDemoConfig
from pipelines.fusion.loader import load_events
from pipelines.fusion.models import CuratedEventRef

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OUTPUT_ROOT = _REPO_ROOT / "output"

# Evidência real já gravada por F4 (prescription) -- ver output/prescription/20260721/.
_REF_REAL = CuratedEventRef(
    modality="prescription",
    feature="prescription",
    run_id="20260721",
    evidence_id="p7-paracetamol-2026-01-01T00-00-07",
    demo_timestamp_s=100.0,
)


def _skip_se_evidencia_ausente():
    sidecar = _OUTPUT_ROOT / "prescription" / "20260721" / f"{_REF_REAL.evidence_id}.json"
    if not sidecar.is_file():
        pytest.skip(f"evidência real de F4 ausente em {sidecar} — rode o pipeline de prescrição")


def _cfg(events: list[CuratedEventRef]) -> PatientDemoConfig:
    return PatientDemoConfig(
        patient_demo_id="demo-teste",
        events=events,
        weights={"video": 0.25, "audio": 0.25, "vitals": 0.25, "prescription": 0.25},
        decay_half_life_s=600.0,
        threshold_amarelo=0.3,
        threshold_vermelho=0.7,
        hysteresis=0.05,
        window_size_s=60.0,
        alert_level="vermelho",
        sns_topic="mm-alerts",
    )


def test_resolve_evento_real_de_prescricao_em_disco():
    _skip_se_evidencia_ausente()
    cfg = _cfg([_REF_REAL])

    events, falhas = load_events(cfg, _OUTPUT_ROOT)

    assert falhas == []
    assert len(events) == 1
    evento = events[0]
    assert evento.modality == "prescription"
    assert evento.demo_timestamp_s == 100.0
    assert evento.severity == 1.0
    assert "paracetamol" in evento.summary
    assert evento.evidence.evidence_id == "p7-paracetamol-2026-01-01T00-00-07"
    assert (
        evento.evidence.source_record_id
        == "mm-test-prescription-bucket-02a6fce9/prescricoes/p7.pdf"
    )
    assert evento.evidence.artifact_path.is_file()
    assert evento.evidence.sidecar_path.is_file()


def test_referencia_inexistente_cai_na_lista_de_falhas_sem_derrubar_a_carga():
    _skip_se_evidencia_ausente()
    ref_inexistente = CuratedEventRef(
        modality="video",
        feature="video_pose",
        run_id="run-que-nao-existe",
        evidence_id="evento-fantasma",
        demo_timestamp_s=5.0,
    )
    cfg = _cfg([_REF_REAL, ref_inexistente])

    events, falhas = load_events(cfg, _OUTPUT_ROOT)

    assert len(events) == 1
    assert events[0].evidence.evidence_id == "p7-paracetamol-2026-01-01T00-00-07"
    assert len(falhas) == 1
    assert "evento-fantasma" in falhas[0]


def test_todas_as_referencias_inexistentes_devolve_lista_de_eventos_vazia(tmp_path):
    ref_inexistente = CuratedEventRef(
        modality="video",
        feature="video_pose",
        run_id="run-x",
        evidence_id="nao-existe",
        demo_timestamp_s=1.0,
    )
    cfg = _cfg([ref_inexistente])

    events, falhas = load_events(cfg, tmp_path)

    assert events == []
    assert len(falhas) == 1
