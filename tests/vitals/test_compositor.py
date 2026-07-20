"""Testes do compositor de timeline (VITALS-07, AD-021)."""

import numpy as np
import pytest

from conftest import escreve_registro
from vitals.compositor import TimelineSpec, compose


def _dataset(tmp_path, **registros) -> object:
    d = tmp_path / "dados"
    d.mkdir(exist_ok=True)
    for nome, kwargs in registros.items():
        escreve_registro(d, nome, **kwargs)
    return d


def test_concatena_dois_registros_na_ordem_declarada(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 100},
        r0002={"ph": 7.01, "n_amostras": 60},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    assert len(t.fhr) == 160
    assert len(t.uc) == 160


def test_conteudo_de_cada_trecho_corresponde_ao_registro_que_a_proveniencia_aponta(tmp_path):
    """Sem amarrar sinal à proveniência, inverter o concatenate passa despercebido
    e toda evidência da timeline apontaria para o registro errado em silêncio."""
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 100, "fhr_base": 140.0},
        r0002={"ph": 7.01, "n_amostras": 60, "fhr_base": 90.0},
    )
    esperado = {"r0001": 140.0, "r0002": 90.0}

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    for seg in t.provenance:
        trecho = t.fhr[seg.start_idx : seg.end_idx]
        assert abs(float(np.mean(trecho)) - esperado[seg.source_record_id]) < 2.0


def test_primeira_amostra_vem_do_primeiro_registro_declarado(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 40, "fhr_base": 140.0},
        r0002={"ph": 7.01, "n_amostras": 40, "fhr_base": 90.0},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    assert abs(float(t.fhr[0]) - 140.0) < 20.0
    assert abs(float(t.fhr[-1]) - 90.0) < 20.0


def test_proveniencia_mapeia_cada_trecho_ao_registro_de_origem(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 100},
        r0002={"ph": 7.01, "n_amostras": 60},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    assert [(s.source_record_id, s.start_idx, s.end_idx) for s in t.provenance] == [
        ("r0001", 0, 100),
        ("r0002", 100, 160),
    ]


def test_trechos_sao_contiguos_sem_gap_nem_sobreposicao(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 100},
        r0002={"ph": 7.01, "n_amostras": 60},
        r0003={"ph": 7.20, "n_amostras": 40},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002", "r0003"]))

    assert len(t.provenance) == 3
    for anterior, seguinte in zip(t.provenance, t.provenance[1:], strict=False):
        assert seguinte.start_idx == anterior.end_idx
    assert t.provenance[0].start_idx == 0
    assert t.provenance[-1].end_idx == len(t.fhr)


def test_rotulo_da_timeline_usa_o_pior_desfecho(tmp_path):
    """A narrativa é de deterioração: o rótulo reflete o estado final, o pH mínimo."""
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 40},
        r0002={"ph": 7.01, "n_amostras": 40},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    assert t.ph == 7.01


def test_mesma_config_produz_a_mesma_timeline(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 40},
        r0002={"ph": 7.01, "n_amostras": 40},
    )
    spec = TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"])

    a, b = compose(spec), compose(spec)

    assert np.array_equal(a.fhr, b.fhr)
    assert np.array_equal(a.uc, b.uc)
    assert a.provenance == b.provenance


def test_ordem_declarada_muda_o_resultado(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 40, "fhr_base": 140.0},
        r0002={"ph": 7.01, "n_amostras": 40, "fhr_base": 90.0},
    )

    direta = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))
    inversa = compose(TimelineSpec(dataset_dir=d, record_ids=["r0002", "r0001"]))

    assert not np.array_equal(direta.fhr, inversa.fhr)
    assert direta.provenance[0].source_record_id == "r0001"
    assert inversa.provenance[0].source_record_id == "r0002"


def test_taxas_divergentes_sao_normalizadas_para_a_do_primeiro(tmp_path):
    d = _dataset(
        tmp_path,
        r0001={"ph": 7.30, "n_amostras": 40, "fs": 4},
        r0002={"ph": 7.01, "n_amostras": 40, "fs": 8},
    )

    t = compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r0002"]))

    assert t.fs == 4.0
    # 40 amostras a 8 Hz = 5 s, que a 4 Hz viram 20 amostras
    assert t.provenance[1].end_idx - t.provenance[1].start_idx == 20


def test_registro_inexistente_e_rejeitado_nomeando_o_id(tmp_path):
    d = _dataset(tmp_path, r0001={"ph": 7.30, "n_amostras": 40})

    with pytest.raises(FileNotFoundError, match="r9999"):
        compose(TimelineSpec(dataset_dir=d, record_ids=["r0001", "r9999"]))


def test_lista_vazia_de_registros_e_rejeitada(tmp_path):
    d = _dataset(tmp_path, r0001={"ph": 7.30, "n_amostras": 40})

    with pytest.raises(ValueError, match="ao menos um"):
        compose(TimelineSpec(dataset_dir=d, record_ids=[]))
