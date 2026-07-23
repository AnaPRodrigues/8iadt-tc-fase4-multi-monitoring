"""Testes de `pipelines.fusion.risk_engine` -- reordenação cronológica e decaimento
temporal (FUSION-02, FUSION-03, FUSION-04, FUSION-14)."""

from pathlib import Path

import pytest

from common.evidence import Evidence
from pipelines.fusion.models import FusionEvent
from pipelines.fusion.risk_engine import decay, sort_events


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
