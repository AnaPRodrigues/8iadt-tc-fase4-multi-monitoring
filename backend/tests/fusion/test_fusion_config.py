"""Testes de `pipelines.fusion.config.load_patient_demo_config`."""

import pytest
import yaml

from pipelines.fusion.config import DEFAULTS, load_patient_demo_config
from pipelines.fusion.models import CuratedEventRef

_EVENTO_MINIMO = {
    "modality": "video",
    "feature": "video_pose",
    "run_id": "run-1",
    "evidence_id": "fall-01-fall",
    "demo_timestamp_s": 10.0,
}


def _escreve(tmp_path, payload):
    p = tmp_path / "demo.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_config_minima_aplica_todos_os_defaults_documentados(tmp_path):
    p = _escreve(
        tmp_path,
        {"patient_demo_id": "demo-1", "events": [_EVENTO_MINIMO]},
    )

    cfg = load_patient_demo_config(p)

    assert (
        cfg.weights
        == DEFAULTS["weights"]
        == {
            "video": 0.25,
            "audio": 0.25,
            "vitals": 0.25,
            "prescription": 0.25,
        }
    )
    assert cfg.decay_half_life_s == DEFAULTS["decay_half_life_s"] == 600.0
    assert cfg.threshold_amarelo == DEFAULTS["threshold_amarelo"] == 0.3
    assert cfg.threshold_vermelho == DEFAULTS["threshold_vermelho"] == 0.7
    assert cfg.hysteresis == DEFAULTS["hysteresis"] == 0.05
    assert cfg.window_size_s == DEFAULTS["window_size_s"] == 60.0
    assert cfg.alert_level == DEFAULTS["alert_level"] == "vermelho"


def test_config_completa_preserva_todos_os_valores_e_converte_events(tmp_path):
    p = _escreve(
        tmp_path,
        {
            "patient_demo_id": "demo-1",
            "events": [
                {
                    "modality": "vitals",
                    "feature": "vitals",
                    "run_id": "20260721",
                    "evidence_id": "0001-zscore-30s",
                    "demo_timestamp_s": 42.5,
                    "severity": 0.8,
                }
            ],
            "weights": {"video": 0.4, "audio": 0.2, "vitals": 0.3, "prescription": 0.1},
            "decay_half_life_s": 120.0,
            "threshold_amarelo": 0.2,
            "threshold_vermelho": 0.6,
            "hysteresis": 0.1,
            "window_size_s": 30.0,
            "alert_level": "amarelo",
        },
    )

    cfg = load_patient_demo_config(p)

    assert cfg.patient_demo_id == "demo-1"
    assert cfg.events == [
        CuratedEventRef(
            modality="vitals",
            feature="vitals",
            run_id="20260721",
            evidence_id="0001-zscore-30s",
            demo_timestamp_s=42.5,
            severity=0.8,
        )
    ]
    assert cfg.weights == {"video": 0.4, "audio": 0.2, "vitals": 0.3, "prescription": 0.1}
    assert cfg.decay_half_life_s == 120.0
    assert cfg.threshold_amarelo == 0.2
    assert cfg.threshold_vermelho == 0.6
    assert cfg.hysteresis == 0.1
    assert cfg.window_size_s == 30.0
    assert cfg.alert_level == "amarelo"


def test_evento_sem_severity_aplica_default_1_0(tmp_path):
    p = _escreve(tmp_path, {"patient_demo_id": "demo-1", "events": [_EVENTO_MINIMO]})

    cfg = load_patient_demo_config(p)

    assert cfg.events[0].severity == 1.0


def test_campo_obrigatorio_ausente_levanta_value_error_nomeando_o_campo(tmp_path):
    p = _escreve(tmp_path, {"events": [_EVENTO_MINIMO]})

    with pytest.raises(ValueError, match="patient_demo_id"):
        load_patient_demo_config(p)


def test_campo_desconhecido_levanta_value_error_nomeando_o_campo(tmp_path):
    p = _escreve(
        tmp_path,
        {"patient_demo_id": "demo-1", "events": [_EVENTO_MINIMO], "campo_invalido": 1},
    )

    with pytest.raises(ValueError, match="campo_invalido"):
        load_patient_demo_config(p)


def test_events_vazio_levanta_value_error(tmp_path):
    p = _escreve(tmp_path, {"patient_demo_id": "demo-1", "events": []})

    with pytest.raises(ValueError, match="events"):
        load_patient_demo_config(p)


def test_modality_fora_do_conjunto_valido_levanta_value_error(tmp_path):
    evento_invalido = {**_EVENTO_MINIMO, "modality": "endoscopia"}
    p = _escreve(tmp_path, {"patient_demo_id": "demo-1", "events": [evento_invalido]})

    with pytest.raises(ValueError, match="endoscopia"):
        load_patient_demo_config(p)
