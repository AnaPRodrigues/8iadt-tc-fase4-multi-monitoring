"""Testes da leitura WFDB (VITALS-01) e do descarte resiliente (VITALS-08)."""

from pathlib import Path

import pytest
from conftest import escreve_registro

from pipelines.vitals.loader import InvalidRecordError, load_dataset, load_record


def test_registro_valido_expoe_sinais_fs_e_ph(registro_valido):
    r = load_record(Path(registro_valido))

    assert r.record_id == "0001"
    assert r.fs == 4.0
    assert r.ph == 7.26
    assert r.fhr.shape == (240,)
    assert r.uc.shape == (240,)


def test_proveniencia_de_registro_simples_cobre_a_serie_inteira(registro_valido):
    r = load_record(Path(registro_valido))

    assert len(r.provenance) == 1
    assert r.provenance[0].source_record_id == "0001"
    assert r.provenance[0].start_idx == 0
    assert r.provenance[0].end_idx == 240


def test_registro_sem_ph_e_rejeitado(tmp_path):
    caminho = escreve_registro(tmp_path, "0003", ph=None)

    with pytest.raises(InvalidRecordError, match="pH"):
        load_record(Path(caminho))


def test_registro_sem_canal_fhr_e_rejeitado(tmp_path):
    caminho = escreve_registro(tmp_path, "0004", sig_name=("ECG", "UC"))

    with pytest.raises(InvalidRecordError, match="FHR"):
        load_record(Path(caminho))


def test_arquivo_corrompido_e_rejeitado(tmp_path):
    (tmp_path / "0005.hea").write_text("isto nao e um header wfdb\n", encoding="utf-8")

    with pytest.raises(InvalidRecordError):
        load_record(tmp_path / "0005")


def test_lote_misto_continua_e_separa_validos_de_falhas(tmp_path):
    escreve_registro(tmp_path, "0001", ph=7.26)
    escreve_registro(tmp_path, "0002", ph=7.01)
    escreve_registro(tmp_path, "0003", ph=None)
    (tmp_path / "0004.hea").write_text("lixo\n", encoding="utf-8")

    registros, falhas = load_dataset(tmp_path)

    assert sorted(r.record_id for r in registros) == ["0001", "0002"]
    assert sorted(f.record_id for f in falhas) == ["0003", "0004"]
    assert all(f.reason for f in falhas)


def test_diretorio_sem_registros_retorna_listas_vazias(tmp_path):
    registros, falhas = load_dataset(tmp_path)

    assert registros == []
    assert falhas == []


def test_descartes_sao_registrados_em_log(tmp_path, caplog):
    escreve_registro(tmp_path, "0001", ph=7.26)
    escreve_registro(tmp_path, "0003", ph=None)

    with caplog.at_level("WARNING", logger="mm.vitals.loader"):
        load_dataset(tmp_path)

    assert "1" in caplog.text
    assert "0003" in caplog.text


def test_diretorio_inexistente_e_rejeitado(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(tmp_path / "nao-existe")
