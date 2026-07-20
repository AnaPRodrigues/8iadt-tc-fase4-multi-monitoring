"""Testes de integração do pipeline ponta a ponta de F3 (VITALS-06, VITALS-08)."""

import json

import pytest
import yaml

from pipelines.vitals.cli import run

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

    # Sem esta guarda o teste passa por vacuidade quando o pipeline gera zero evidências.
    assert sidecars, "o cenário deve produzir ao menos uma evidência"

    detectores_vistos = set()

    for side in sidecars:
        dados_side = json.loads(side.read_text(encoding="utf-8"))
        meta = dados_side["metadata"]

        assert dados_side["source_record_id"] == "0001"
        assert (saida / dados_side["artifact"]).is_file()
        assert meta["ph"] == 7.01
        assert meta["record_id"] == "0001"
        assert meta["source_record_id"] == "0001"
        assert meta["end_s"] > meta["start_s"]

        # O nome do arquivo é derivado do evento: se os metadados discordarem dele
        # sobre detector ou janela, a evidência está rotulada errado.
        assert side.stem == f"0001-{meta['detector']}-{meta['start_s']:.0f}s"
        detectores_vistos.add(meta["detector"])

    # Rotular tudo com um único detector invalidaria as métricas por detector.
    assert detectores_vistos == {"zscore", "isolation_forest"}


def _recomputa_por_detector(dados, cfg_path):
    """Refaz o pipeline fora do CLI para servir de fonte de verdade independente.

    Comparar o nome do arquivo de evidência com seus próprios metadados é tautológico:
    ambos derivam do mesmo evento. Só recomputando é possível afirmar que a evidência
    atribuída a um detector corresponde às janelas que AQUELE detector marcou.
    """
    from common.config import load_config
    from pipelines.vitals.cli import _limpa
    from pipelines.vitals.detectors import IsolationForestDetector, RollingZScoreDetector
    from pipelines.vitals.features import extract
    from pipelines.vitals.loader import load_dataset
    from pipelines.vitals.windowing import make_windows

    # Ler a mesma config que o CLI leu, em vez de repetir valores que só
    # coincidiriam com ela por serem os defaults.
    cfg = load_config(cfg_path)

    registros, _ = load_dataset(dados)
    record = registros[0]
    limpo, mask = _limpa(record)
    janelas = make_windows(limpo, cfg.window_size_s, cfg.window_stride_s, mask)
    features = [extract(j, fs=limpo.fs) for j in janelas]

    esperado: dict[str, dict[float, float]] = {}
    for det in (
        RollingZScoreDetector(threshold=cfg.zscore_threshold),
        IsolationForestDetector(contamination=cfg.iforest_contamination, seed=cfg.seed),
    ):
        marcadas = {
            j.start_s: s
            for j, f, s in zip(janelas, det.flag(features), det.score(features), strict=True)
            if f
        }
        # Só registrar o detector se ele de fato marcou algo: criar a chave
        # incondicionalmente faria um conjunto vazio parecer concordância.
        if marcadas:
            esperado[det.name] = marcadas
    return esperado


def test_evidencia_corresponde_as_janelas_que_aquele_detector_marcou(tmp_path, escritor):
    """Fecha V1 e V2: fidelidade do detector E do score, contra fonte independente."""
    dados = tmp_path / "dados"
    dados.mkdir()
    escritor(dados, "0001", ph=7.01, n_amostras=N_AMOSTRAS)
    cfg = _config(tmp_path, dados)

    run(cfg, run_id="teste")

    saida = tmp_path / "out" / "vitals" / "teste"
    sidecars = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in saida.glob("*.json")
        if p.name != "metrics.json"
    ]
    assert sidecars

    esperado = _recomputa_por_detector(dados, cfg)

    obtido: dict[str, dict[float, float]] = {}
    for s in sidecars:
        meta = s["metadata"]
        obtido.setdefault(meta["detector"], {})[meta["start_s"]] = meta["score"]

    assert set(obtido) == set(esperado), "conjunto de detectores na evidência diverge"

    for nome, janelas_esperadas in esperado.items():
        assert set(obtido[nome]) == set(janelas_esperadas), (
            f"janelas atribuídas a {nome} não são as que ele marcou"
        )
        for start_s, score_esperado in janelas_esperadas.items():
            assert obtido[nome][start_s] == pytest.approx(score_esperado), (
                f"score de {nome} em {start_s}s foi alterado entre detector e evidência"
            )


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
