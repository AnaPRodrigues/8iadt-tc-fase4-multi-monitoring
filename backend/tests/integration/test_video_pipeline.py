"""Testes de integração do pipeline ponta a ponta da raia pose (queda) de vídeo."""

import json
import logging
from pathlib import Path

import pytest
import yaml

from pipelines.video.cli import main, run

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[3]
_URFD_DIR = _REPO_ROOT / "data" / "urfd"


def _config(tmp_path: Path, dataset_dir: Path, **overrides) -> Path:
    payload = {
        "dataset_dir": str(dataset_dir),
        "output_root": str(tmp_path / "out"),
        "model_cache_dir": str(_REPO_ROOT / "models"),
        **overrides,
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def _skip_se_dataset_ausente():
    if not _URFD_DIR.is_dir():
        pytest.skip(f"dataset URFD ausente em {_URFD_DIR} — rode `make data`")


def test_sequencia_de_queda_real_produz_metricas_e_evidencia_real(tmp_path):
    _skip_se_dataset_ausente()
    cfg = _config(tmp_path, _URFD_DIR, sequences=["fall-01"])

    assert run(cfg, run_id="teste-fall") == 0

    saida = tmp_path / "out" / "video_pose" / "teste-fall"
    assert (saida / "metrics.json").is_file()

    sidecars = list(saida.glob("fall-01-fall.json"))
    assert sidecars, "sequência fall-01 deveria disparar evidência de queda"
    sidecar = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert sidecar["metadata"]["seq_id"] == "fall-01"
    assert (saida / sidecar["artifact"]).is_file()


def test_sequencia_adl_real_nao_gera_evidencia_de_queda(tmp_path):
    _skip_se_dataset_ausente()
    cfg = _config(tmp_path, _URFD_DIR, sequences=["adl-01"])

    assert run(cfg, run_id="teste-adl") == 0

    saida = tmp_path / "out" / "video_pose" / "teste-adl"
    metrics = json.loads((saida / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["detector"] == "pose_fall"
    assert list(saida.glob("adl-01-fall.json")) == []


def test_run_id_none_gera_run_id_automatico_com_evidencia_real(tmp_path):
    _skip_se_dataset_ausente()
    cfg = _config(tmp_path, _URFD_DIR, sequences=["fall-01"])

    assert run(cfg, run_id=None) == 0

    saida_root = tmp_path / "out" / "video_pose"
    run_dirs = list(saida_root.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "metrics.json").is_file()


def test_dataset_urfd_ausente_produz_dica_de_make_data(tmp_path, caplog):
    cfg = _config(tmp_path, tmp_path / "nao-existe", sequences=["fall-01"])

    with caplog.at_level(logging.ERROR):
        codigo = main(["--config", str(cfg), "--run-id", "teste"])

    assert codigo == 2
    assert "make data" in caplog.text
