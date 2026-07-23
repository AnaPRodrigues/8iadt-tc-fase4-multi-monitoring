"""Testes do adaptador opcional MIT-BIH."""

import numpy as np
import pytest
import wfdb

from pipelines.vitals.mitbih import (
    MITBIH_ANNOTATOR,
    load_mitbih_dataset,
    load_mitbih_record,
    mitbih_disponivel,
)


def _escreve_ecg(directory, nome="100", n=400, com_anotacao=True, simbolos=None):
    rng = np.random.default_rng(0)
    sinal = rng.normal(0.0, 0.2, (n, 1))
    wfdb.wrsamp(
        nome, fs=360, units=["mV"], sig_name=["MLII"],
        p_signal=sinal, fmt=["16"], write_dir=str(directory),
    )
    if com_anotacao:
        simbolos = simbolos or ["N", "V", "N"]
        wfdb.wrann(
            nome, MITBIH_ANNOTATOR,
            sample=np.array([50, 150, 250][: len(simbolos)]),
            symbol=simbolos,
            write_dir=str(directory),
        )
    return directory / nome


def test_carrega_ecg_e_anotacoes(tmp_path):
    _escreve_ecg(tmp_path)

    r = load_mitbih_record(tmp_path / "100")

    assert r.record_id == "100"
    assert r.fs == 360.0
    assert r.ecg.shape == (400,)
    assert len(r.annotations) == 3


def test_batimentos_anomalos_sao_identificados_pelo_simbolo(tmp_path):
    """No MIT-BIH, 'N' é batimento normal; outros símbolos indicam arritmia."""
    _escreve_ecg(tmp_path, simbolos=["N", "V", "N"])

    r = load_mitbih_record(tmp_path / "100")

    assert r.anomalous_beats == 1
    assert r.has_anomaly is True


def test_registro_so_com_batimentos_normais_nao_tem_anomalia(tmp_path):
    _escreve_ecg(tmp_path, simbolos=["N", "N", "N"])

    r = load_mitbih_record(tmp_path / "100")

    assert r.anomalous_beats == 0
    assert r.has_anomaly is False


def test_dataset_ausente_e_reportado_como_indisponivel(tmp_path):
    assert mitbih_disponivel(tmp_path / "nao-existe") is False


def test_diretorio_sem_registros_e_reportado_como_indisponivel(tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()

    assert mitbih_disponivel(vazio) is False


def test_dataset_presente_e_reportado_como_disponivel(tmp_path):
    _escreve_ecg(tmp_path)

    assert mitbih_disponivel(tmp_path) is True


def test_dataset_ausente_devolve_lista_vazia_sem_excecao(tmp_path):
    """Ausência do dataset opcional não pode interromper o pipeline."""
    assert load_mitbih_dataset(tmp_path / "nao-existe") == []


def test_dataset_carrega_todos_os_registros_disponiveis(tmp_path):
    _escreve_ecg(tmp_path, nome="100", simbolos=["N", "V", "N"])
    _escreve_ecg(tmp_path, nome="101", simbolos=["N", "N", "N"])

    registros = load_mitbih_dataset(tmp_path)

    assert sorted(r.record_id for r in registros) == ["100", "101"]
    assert sum(r.anomalous_beats for r in registros) == 1


def test_registro_ilegivel_e_ignorado_sem_derrubar_o_lote(tmp_path):
    _escreve_ecg(tmp_path, nome="100", simbolos=["N", "V"])
    (tmp_path / "999.atr").write_bytes(b"lixo")

    registros = load_mitbih_dataset(tmp_path)

    assert [r.record_id for r in registros] == ["100"]


def test_registro_sem_anotacao_e_rejeitado(tmp_path):
    _escreve_ecg(tmp_path, com_anotacao=False)

    with pytest.raises(FileNotFoundError, match="anota"):
        load_mitbih_record(tmp_path / "100")
