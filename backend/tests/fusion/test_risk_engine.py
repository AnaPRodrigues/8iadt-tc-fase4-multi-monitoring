"""Testes de `pipelines.fusion.risk_engine` -- reordenação cronológica, decaimento
temporal e risk score ponderado por janela (FUSION-02, FUSION-03, FUSION-04, FUSION-14)."""

from pathlib import Path

import pytest

from common.evidence import Evidence
from pipelines.fusion.config import PatientDemoConfig
from pipelines.fusion.models import FusionEvent
from pipelines.fusion.risk_engine import compute_timeline, decay, score_at, sort_events


def _cfg(**overrides) -> PatientDemoConfig:
    defaults = {
        "patient_demo_id": "demo-teste",
        "events": [],
        "weights": {"video": 0.25, "audio": 0.25, "vitals": 0.25, "prescription": 0.25},
        "decay_half_life_s": 600.0,
        "threshold_amarelo": 0.3,
        "threshold_vermelho": 0.7,
        "hysteresis": 0.05,
        "window_size_s": 60.0,
        "alert_level": "vermelho",
    }
    return PatientDemoConfig(**{**defaults, **overrides})


def _evento(modality: str, t: float, severity: float = 1.0) -> FusionEvent:
    return FusionEvent(
        modality=modality,
        demo_timestamp_s=t,
        severity=severity,
        summary=f"evento {modality} em {t}",
        evidence=Evidence(
            feature=modality,
            run_id="run-teste",
            evidence_id=f"{modality}-{t}",
            source_record_id="rec-1",
            artifact_path=Path(f"output/{modality}/run-teste/{modality}-{t}.png"),
            sidecar_path=Path(f"output/{modality}/run-teste/{modality}-{t}.json"),
        ),
    )


def test_sort_events_reordena_lista_fora_de_ordem_cronologica():
    fora_de_ordem = [
        _evento("prescription", 30.0),
        _evento("video", 5.0),
        _evento("audio", 20.0),
        _evento("vitals", 10.0),
    ]

    ordenado = sort_events(fora_de_ordem)

    assert [e.demo_timestamp_s for e in ordenado] == [5.0, 10.0, 20.0, 30.0]
    assert [e.modality for e in ordenado] == ["video", "vitals", "audio", "prescription"]


def test_sort_events_com_eventos_de_multiplas_modalidades_fora_de_ordem():
    eventos = [_evento("audio", 15.0), _evento("video", 3.0), _evento("vitals", 8.0)]

    ordenado = sort_events(eventos)

    assert ordenado[0].modality == "video"
    assert ordenado[1].modality == "vitals"
    assert ordenado[2].modality == "audio"


def test_sort_events_nao_modifica_a_lista_original():
    original = [_evento("audio", 15.0), _evento("video", 3.0)]
    original_copia = list(original)

    sort_events(original)

    assert original == original_copia


def test_decay_em_elapsed_zero_e_1():
    assert decay(0.0, 600.0) == 1.0


def test_decay_na_meia_vida_e_0_5():
    assert decay(600.0, 600.0) == pytest.approx(0.5)


def test_decay_em_duas_meias_vidas_e_0_25():
    assert decay(1200.0, 600.0) == pytest.approx(0.25)


def test_decay_e_monotonicamente_decrescente():
    valores = [decay(t, 600.0) for t in [0.0, 100.0, 300.0, 600.0, 1200.0, 3600.0]]

    assert valores == sorted(valores, reverse=True)
    assert len(set(valores)) == len(valores)  # estritamente decrescente, sem empates


def test_score_at_soma_peso_severidade_decay_do_evento_mais_recente_por_modalidade():
    weights = {"video": 0.4, "audio": 0.1, "vitals": 0.3, "prescription": 0.2}
    half_life_s = 600.0
    eventos = [
        _evento("video", t=0.0, severity=1.0),
        _evento("vitals", t=100.0, severity=0.5),
    ]

    ponto = score_at(200.0, eventos, weights, half_life_s)

    esperado_video = 0.4 * 1.0 * decay(200.0, half_life_s)
    esperado_vitals = 0.3 * 0.5 * decay(100.0, half_life_s)
    assert ponto.contributions["video"] == pytest.approx(esperado_video)
    assert ponto.contributions["vitals"] == pytest.approx(esperado_vitals)
    assert ponto.score == pytest.approx(esperado_video + esperado_vitals)


def test_score_at_usa_o_evento_mais_recente_da_modalidade_ate_t_nao_o_mais_antigo():
    weights = {"video": 1.0}
    eventos = [
        _evento("video", t=0.0, severity=1.0),
        _evento("video", t=50.0, severity=1.0),
    ]

    ponto = score_at(60.0, eventos, weights, half_life_s=600.0)

    # Contribuição precisa vir do evento em t=50 (o mais recente <= 60), não do t=0 --
    # senão a decaimento aplicada seria diferente (60s decorridos em vez de 10s).
    assert ponto.contributions["video"] == pytest.approx(decay(10.0, 600.0))
    assert ponto.contributing_events == [eventos[1]]


def test_score_at_modalidade_sem_evento_ate_t_entra_em_missing_sem_contribuir_como_zero():
    weights = {"video": 0.25, "audio": 0.25, "vitals": 0.25, "prescription": 0.25}
    eventos = [_evento("video", t=0.0)]

    ponto = score_at(10.0, eventos, weights, half_life_s=600.0)

    assert ponto.missing_modalities == ["audio", "vitals", "prescription"]
    assert "audio" not in ponto.contributions
    assert "vitals" not in ponto.contributions
    assert "prescription" not in ponto.contributions
    assert "video" in ponto.contributions


def test_score_at_evento_futuro_apos_t_nao_conta_como_disponivel():
    weights = {"video": 1.0}
    eventos = [_evento("video", t=50.0)]

    ponto = score_at(10.0, eventos, weights, half_life_s=600.0)

    assert ponto.missing_modalities == ["video"]
    assert ponto.score == 0.0


def test_compute_timeline_varre_de_t0_ate_ultimo_timestamp_mais_cauda_em_passos_de_window_size():
    cfg = _cfg(window_size_s=10.0)
    eventos = [_evento("video", t=25.0)]

    pontos = compute_timeline(eventos, cfg)

    # último demo_timestamp_s=25 + cauda de 10 = 35; passos de 10 a partir de 0.
    assert [p.t for p in pontos] == [0.0, 10.0, 20.0, 30.0]


def test_compute_timeline_sem_eventos_devolve_lista_vazia():
    cfg = _cfg(window_size_s=10.0)

    assert compute_timeline([], cfg) == []


def test_compute_timeline_paciente_demo_sem_uma_modalidade_confirma_missing_desde_t_zero():
    # Edge case FUSION-14: paciente-demo sem vídeo no cenário inteiro -- "video" precisa
    # aparecer em `missing_modalities` desde o primeiro ponto (t=0), não só depois.
    cfg = _cfg(window_size_s=10.0)
    eventos = [_evento("audio", t=0.0), _evento("vitals", t=5.0), _evento("prescription", t=5.0)]

    pontos = compute_timeline(eventos, cfg)

    assert pontos[0].t == 0.0
    assert "video" in pontos[0].missing_modalities
    assert all("video" in p.missing_modalities for p in pontos)
