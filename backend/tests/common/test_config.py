"""Testes de core.config — carga declarativa usada pelo CLI e pelo compositor."""

import pytest
import yaml

from common.config import DEFAULTS, load_config


def _escreve(tmp_path, payload):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_config_completa_preserva_todos_os_valores(tmp_path):
    p = _escreve(
        tmp_path,
        {
            "dataset_dir": "data/ctu-uhb",
            "window_size_s": 120.0,
            "window_stride_s": 60.0,
            "zscore_threshold": 2.5,
            "iforest_contamination": 0.2,
            "tau": 0.3,
            "seed": 7,
            "output_root": "saida",
        },
    )

    cfg = load_config(p)

    assert cfg.dataset_dir.as_posix() == "data/ctu-uhb"
    assert cfg.window_size_s == 120.0
    assert cfg.window_stride_s == 60.0
    assert cfg.zscore_threshold == 2.5
    assert cfg.iforest_contamination == 0.2
    assert cfg.tau == 0.3
    assert cfg.seed == 7
    assert cfg.output_root.as_posix() == "saida"


def test_config_minima_aplica_defaults_documentados(tmp_path):
    p = _escreve(tmp_path, {"dataset_dir": "data/ctu-uhb"})

    cfg = load_config(p)

    assert cfg.tau == 0.15
    assert cfg.window_size_s == DEFAULTS["window_size_s"]
    assert cfg.window_stride_s == DEFAULTS["window_stride_s"]
    assert cfg.zscore_threshold == DEFAULTS["zscore_threshold"]
    assert cfg.iforest_contamination == DEFAULTS["iforest_contamination"]
    assert cfg.seed == DEFAULTS["seed"]


def test_campo_obrigatorio_ausente_nomeia_o_campo(tmp_path):
    p = _escreve(tmp_path, {"tau": 0.2})

    with pytest.raises(ValueError, match="dataset_dir"):
        load_config(p)


def test_tipo_invalido_nomeia_o_campo(tmp_path):
    p = _escreve(tmp_path, {"dataset_dir": "data/x", "tau": "nao-numerico"})

    with pytest.raises(ValueError, match="tau"):
        load_config(p)


def test_campo_desconhecido_e_rejeitado(tmp_path):
    p = _escreve(tmp_path, {"dataset_dir": "data/x", "taus": 0.2})

    with pytest.raises(ValueError, match="taus"):
        load_config(p)


def test_arquivo_inexistente_e_rejeitado(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nao-existe.yaml")
