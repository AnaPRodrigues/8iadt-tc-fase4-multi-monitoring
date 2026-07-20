"""Testes de integração do pipeline ponta a ponta de F3 (VITALS-06, VITALS-08)."""

import json

import pytest
import yaml

from vitals.cli import run

pytestmark = pytest.mark.integration

N_AMOSTRAS = 2400  # 600 s a 4 Hz — suficiente para dezenas de janelas


def _config(tmp_path, dataset_dir, **overrides):
    payload = {
        "dataset_dir": str(dataset_dir),
        "window_size_s": 20.0,
        "window_stride_s": 10.0,
        "output_root": str(tmp_path / "out"),
        **overrides,
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_pipeline_completo_gera_metricas_e_evidencias(tmp_path, escritor):
    dados = tmp_path / "dados"
    dados.mkdir()
    escritor(dados, "0001", ph=7.30, n_amostras=N_AMOSTRAS, fhr_base=140.0)
    escritor(dados, "0002", ph=7.01, n_amostras=N_AMOSTRAS, fhr_base=100.0)
    cfg = _config(tmp_path, dados)

    assert run(cfg, run_id="teste") == 0

    saida = tmp_path / "out" / "vitals" / "teste"
    metrics = json.loads((saida / "metrics.json").read_text(encoding="utf-8"))

    assert metrics["n_records"] == 2
    assert metrics["n_pathological"] == 1
    assert metrics["prevalence"] == pytest.approx(0.5)
    assert {m["detector"] for m in metrics["metrics"]} == {"zscore", "isolation_forest"}


def test_toda_evidencia_tem_artefato_e_sidecar(tmp_path, escritor):
    dados = tmp_path / "dados"
    dados.mkdir()
    escritor(dados, "0001", ph=7.01, n_amostras=N_AMOSTRAS)
    cfg = _config(tmp_path, dados)

    run(cfg, run_id="teste")

    saida = tmp_path / "out" / "vitals" / "teste"
    sidecars = [p for p in saida.glob("*.json") if p.name != "metrics.json"]

    for side in sidecars:
        dados_side = json.loads(side.read_text(encoding="utf-8"))
        assert dados_side["source_record_id"] == "0001"
        assert (saida / dados_side["artifact"]).is_file()
        assert "ph" in dados_side["metadata"]


def test_dataset_ausente_retorna_erro_sem_excecao(tmp_path):
    cfg = _config(tmp_path, tmp_path / "nao-existe")

    with pytest.raises(FileNotFoundError):
        run(cfg, run_id="teste")


def test_dataset_vazio_retorna_codigo_de_erro(tmp_path):
    dados = tmp_path / "vazio"
    dados.mkdir()

    assert run(_config(tmp_path, dados), run_id="teste") == 1


def test_registro_corrompido_no_lote_nao_impede_o_restante(tmp_path, escritor):
    """VITALS-08: um header ilegível no meio do lote não pode custar a execução."""
    dados = tmp_path / "dados"
    dados.mkdir()
    escritor(dados, "0001", ph=7.30, n_amostras=N_AMOSTRAS)
    escritor(dados, "0002", ph=7.01, n_amostras=N_AMOSTRAS)
    (dados / "0003.hea").write_text("nao e um header wfdb\n", encoding="utf-8")

    assert run(_config(tmp_path, dados), run_id="teste") == 0

    metrics = json.loads(
        (tmp_path / "out" / "vitals" / "teste" / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["n_records"] == 2


def test_execucao_e_reprodutivel_com_a_mesma_seed(tmp_path, escritor):
    dados = tmp_path / "dados"
    dados.mkdir()
    escritor(dados, "0001", ph=7.01, n_amostras=N_AMOSTRAS)
    cfg = _config(tmp_path, dados)

    run(cfg, run_id="a")
    run(cfg, run_id="b")

    base = tmp_path / "out" / "vitals"
    a = json.loads((base / "a" / "metrics.json").read_text(encoding="utf-8"))
    b = json.loads((base / "b" / "metrics.json").read_text(encoding="utf-8"))

    assert a == b
