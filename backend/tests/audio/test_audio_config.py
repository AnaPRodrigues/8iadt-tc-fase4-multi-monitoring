"""Testes da configuração declarativa de F2 (AUDIO-01..14, fundação)."""

import pytest
import yaml

from pipelines.audio.config import DEFAULTS, load_config


def _escreve(tmp_path, payload):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_config_completa_preserva_todos_os_valores(tmp_path):
    p = _escreve(
        tmp_path,
        {
            "icbhi_dataset_dir": "data/icbhi",
            "icbhi_max_patients": 10,
            "consult_audio_paths": ["a.wav", "b.wav"],
            "critical_terms_path": "configs/critical_terms.yaml",
            "whisper_model_size": "tiny",
            "no_speech_threshold": 0.5,
            "sentiment_threshold": 0.3,
            "fatigue_threshold": 1.5,
            "seed": 7,
            "output_root": "saida",
        },
    )

    cfg = load_config(p)

    assert cfg.icbhi_dataset_dir.as_posix() == "data/icbhi"
    assert cfg.icbhi_max_patients == 10
    assert [p.as_posix() for p in cfg.consult_audio_paths] == ["a.wav", "b.wav"]
    assert cfg.critical_terms_path.as_posix() == "configs/critical_terms.yaml"
    assert cfg.whisper_model_size == "tiny"
    assert cfg.no_speech_threshold == 0.5
    assert cfg.sentiment_threshold == 0.3
    assert cfg.fatigue_threshold == 1.5
    assert cfg.seed == 7
    assert cfg.output_root.as_posix() == "saida"


def test_config_minima_aplica_defaults_documentados(tmp_path):
    p = _escreve(tmp_path, {"icbhi_dataset_dir": "data/icbhi"})

    cfg = load_config(p)

    assert cfg.icbhi_max_patients == DEFAULTS["icbhi_max_patients"] == 40
    assert cfg.consult_audio_paths == []
    assert cfg.critical_terms_path is None
    assert cfg.whisper_model_size == DEFAULTS["whisper_model_size"] == "small"
    assert cfg.no_speech_threshold == DEFAULTS["no_speech_threshold"] == 0.6
    assert cfg.sentiment_threshold == DEFAULTS["sentiment_threshold"] == 0.2
    assert cfg.fatigue_threshold == DEFAULTS["fatigue_threshold"] == 1.0
    assert cfg.seed == DEFAULTS["seed"] == 42
    assert cfg.output_root.as_posix() == "output"


def test_campo_obrigatorio_ausente_levanta_value_error_nomeando_o_campo(tmp_path):
    p = _escreve(tmp_path, {"seed": 1})

    with pytest.raises(ValueError, match="icbhi_dataset_dir"):
        load_config(p)


def test_campo_desconhecido_levanta_value_error_nomeando_o_campo(tmp_path):
    p = _escreve(tmp_path, {"icbhi_dataset_dir": "data/icbhi", "icbhi_max_patient": 5})

    with pytest.raises(ValueError, match="icbhi_max_patient"):
        load_config(p)


def test_consult_audio_paths_vazio_e_valido(tmp_path):
    p = _escreve(
        tmp_path, {"icbhi_dataset_dir": "data/icbhi", "consult_audio_paths": []}
    )

    cfg = load_config(p)

    assert cfg.consult_audio_paths == []
