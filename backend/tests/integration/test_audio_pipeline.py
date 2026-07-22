"""Testes de integração do pipeline ponta a ponta de F2 (T13)."""

import json
import logging
from pathlib import Path

import pytest
import yaml

from pipelines.audio.cli import main, run

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ICBHI_DIR = _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"


def _config(tmp_path: Path, dataset_dir: Path, **overrides) -> Path:
    payload = {
        "icbhi_dataset_dir": str(dataset_dir),
        "icbhi_max_patients": 40,
        "output_root": str(tmp_path / "out"),
        "seed": 42,
        **overrides,
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def _skip_se_dataset_ausente():
    if not _ICBHI_DIR.is_dir():
        pytest.skip(f"dataset ICBHI ausente em {_ICBHI_DIR} — rode `make data`")


def test_p1_sobre_subconjunto_curado_real_produz_metricas_e_evidencia(tmp_path):
    _skip_se_dataset_ausente()
    cfg = _config(tmp_path, _ICBHI_DIR)

    assert run(cfg, run_id="teste-p1") == 0

    saida = tmp_path / "out" / "audio" / "teste-p1"
    metrics = json.loads((saida / "metrics.json").read_text(encoding="utf-8"))

    assert {m["detector"] for m in metrics} == {"normal", "crackle", "wheeze", "both"}

    sidecars = [
        p for p in saida.glob("*.json") if p.name not in ("metrics.json",) and "cycle" in p.name
    ]
    assert sidecars, "deve haver ao menos uma evidência de ciclo anômalo"
    for side in sidecars:
        meta = json.loads(side.read_text(encoding="utf-8"))["metadata"]
        assert meta["predicted_label"] != "normal"


def test_p2_p3_com_audio_icbhi_real_sem_fala_grava_resumo_reliable_false(tmp_path):
    _skip_se_dataset_ausente()
    wav_sem_fala = sorted(_ICBHI_DIR.glob("*.wav"))[0]
    cfg = _config(
        tmp_path,
        _ICBHI_DIR,
        icbhi_max_patients=5,  # P1 mínimo: o foco do teste é a raia P2/P3
        consult_audio_paths=[str(wav_sem_fala)],
        whisper_model_size="tiny",
    )

    assert run(cfg, run_id="teste-p2p3") == 0

    saida = tmp_path / "out" / "audio" / "teste-p2p3"
    resumo_path = saida / f"{wav_sem_fala.stem}-summary.json"
    assert resumo_path.is_file()
    resumo = json.loads(resumo_path.read_text(encoding="utf-8"))
    assert resumo["reliable"] is False
    assert resumo["critical_terms_found"] == 0

    evidencias_de_termo = list(saida.glob(f"{wav_sem_fala.stem}-term-*.json"))
    assert evidencias_de_termo == []  # sem falso positivo de termo crítico


def test_consult_audio_paths_vazio_roda_so_p1_ate_o_fim(tmp_path):
    _skip_se_dataset_ausente()
    cfg = _config(tmp_path, _ICBHI_DIR, icbhi_max_patients=5, consult_audio_paths=[])

    assert run(cfg, run_id="teste-so-p1") == 0

    saida = tmp_path / "out" / "audio" / "teste-so-p1"
    assert (saida / "metrics.json").is_file()
    assert list(saida.glob("*-summary.json")) == []


def test_dataset_icbhi_ausente_produz_dica_de_make_data(tmp_path, caplog):
    cfg = _config(tmp_path, tmp_path / "nao-existe")

    with caplog.at_level(logging.ERROR):
        codigo = main(["--config", str(cfg), "--run-id", "teste"])

    assert codigo == 2
    assert "make data" in caplog.text
