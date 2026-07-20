"""Integração do cenário de timeline composta (VITALS-07)."""

import json

import pytest
import yaml

from vitals.cli import run

pytestmark = pytest.mark.integration

N = 1200  # 300 s a 4 Hz


def _dataset(tmp_path, escritor):
    d = tmp_path / "dados"
    d.mkdir()
    escritor(d, "normal01", ph=7.30, n_amostras=N, fhr_base=140.0)
    escritor(d, "patol01", ph=7.01, n_amostras=N, fhr_base=95.0)
    return d


def _config(tmp_path, dados, timeline):
    payload = {
        "dataset_dir": str(dados),
        "window_size_s": 20.0,
        "window_stride_s": 10.0,
        "output_root": str(tmp_path / "out"),
        "timeline": timeline,
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return p


def test_cenario_normal_para_patologico_roda_ponta_a_ponta(tmp_path, escritor):
    dados = _dataset(tmp_path, escritor)
    cfg = _config(tmp_path, dados, ["normal01", "patol01"])

    assert run(cfg, run_id="tl") == 0

    metrics = json.loads(
        (tmp_path / "out" / "vitals" / "tl" / "metrics.json").read_text(encoding="utf-8")
    )
    # A timeline é um único "paciente" cujo rótulo é o pior desfecho (pH 7.01)
    assert metrics["n_records"] == 1
    assert metrics["n_pathological"] == 1


def test_evidencia_atribui_a_anomalia_ao_registro_de_origem(tmp_path, escritor):
    dados = _dataset(tmp_path, escritor)
    cfg = _config(tmp_path, dados, ["normal01", "patol01"])

    run(cfg, run_id="tl")

    saida = tmp_path / "out" / "vitals" / "tl"
    sidecars = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in saida.glob("*.json")
        if p.name != "metrics.json"
    ]

    assert sidecars, "o cenário deve produzir ao menos uma evidência"
    origens = {s["source_record_id"] for s in sidecars}
    # Nenhuma evidência pode ser atribuída ao id sintético da timeline
    assert origens <= {"normal01", "patol01"}
    assert "timeline-demo" not in origens


def test_anomalias_no_segundo_trecho_apontam_para_o_registro_patologico(tmp_path, escritor):
    dados = _dataset(tmp_path, escritor)
    cfg = _config(tmp_path, dados, ["normal01", "patol01"])

    run(cfg, run_id="tl")

    saida = tmp_path / "out" / "vitals" / "tl"
    sidecars = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in saida.glob("*.json")
        if p.name != "metrics.json"
    ]
    # 300 s é a fronteira entre os dois trechos concatenados
    tardias = [s for s in sidecars if s["metadata"]["start_s"] >= 300.0]

    assert all(s["source_record_id"] == "patol01" for s in tardias)


def test_timeline_com_registro_inexistente_falha_nomeando_o_id(tmp_path, escritor):
    dados = _dataset(tmp_path, escritor)
    cfg = _config(tmp_path, dados, ["normal01", "inexistente99"])

    with pytest.raises(FileNotFoundError, match="inexistente99"):
        run(cfg, run_id="tl")
