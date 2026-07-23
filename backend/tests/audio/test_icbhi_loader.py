"""Testes do loader ICBHI."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from pipelines.audio.icbhi_loader import (
    load_cycles,
    load_dataset,
    parse_filename,
    select_subset,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ICBHI_DIR = _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"


def _wav(path: Path, seconds: float = 1.0, sr: int = 4000) -> None:
    sf.write(str(path), np.zeros(int(seconds * sr)), sr)


def test_parse_filename_extrai_os_5_campos_de_nomes_reais_do_dataset():
    meta = parse_filename("103_2b2_Ar_mc_LittC2SE.wav")

    assert meta.patient_id == "103"
    assert meta.recording_index == "2b2"
    assert meta.chest_location == "Ar"
    assert meta.acquisition_mode == "mc"
    assert meta.equipment == "LittC2SE"

    meta2 = parse_filename("104_1b1_Ll_sc_Litt3200.wav")

    assert meta2.patient_id == "104"
    assert meta2.recording_index == "1b1"
    assert meta2.chest_location == "Ll"
    assert meta2.acquisition_mode == "sc"
    assert meta2.equipment == "Litt3200"


def test_ciclo_crackle_e_wheeze_simultaneos_vira_classe_both(tmp_path):
    wav = tmp_path / "999_1b1_Al_sc_Meditron.wav"
    _wav(wav)
    txt = tmp_path / "999_1b1_Al_sc_Meditron.txt"
    txt.write_text(
        "0.0\t1.0\t0\t0\n"
        "1.0\t2.0\t1\t0\n"
        "2.0\t3.0\t0\t1\n"
        "3.0\t4.0\t1\t1\n",
        encoding="utf-8",
    )

    cycles = load_cycles(txt, wav)

    labels = [c.label for c in cycles]
    assert labels == ["normal", "crackle", "wheeze", "both"]


def test_linha_de_anotacao_malformada_e_excluida_do_resultado(tmp_path):
    wav = tmp_path / "999_1b1_Al_sc_Meditron.wav"
    _wav(wav)
    txt = tmp_path / "999_1b1_Al_sc_Meditron.txt"
    txt.write_text(
        "0.0\t1.0\t0\t0\n"  # válida
        "1.0\t2.0\t1\n"  # coluna faltando
        "nao-numerico\t3.0\t0\t0\n"  # start ilegível
        "3.0\t4.0\t1\t0\n",  # válida
        encoding="utf-8",
    )

    cycles = load_cycles(txt, wav)

    assert len(cycles) == 2
    assert [c.label for c in cycles] == ["normal", "crackle"]


def test_wav_corrompido_e_pulado_e_reportado_sem_derrubar_o_lote(tmp_path):
    wav_ok = tmp_path / "100_1b1_Al_sc_Meditron.wav"
    _wav(wav_ok)
    (tmp_path / "100_1b1_Al_sc_Meditron.txt").write_text("0.0\t1.0\t0\t0\n", encoding="utf-8")

    wav_corrompido = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    wav_corrompido.write_bytes(b"nao e um wav valido")
    (tmp_path / "101_1b1_Al_sc_Meditron.txt").write_text("0.0\t1.0\t0\t0\n", encoding="utf-8")

    cycles, falhas = load_dataset(tmp_path)

    assert [c.record_id for c in cycles] == ["100_1b1_Al_sc_Meditron"]
    assert falhas == ["101_1b1_Al_sc_Meditron.wav"]


def test_select_subset_com_mesma_seed_e_deterministico():
    cycles_by_patient = {
        pid: [
            _ciclo_fake(pid, i) for i in range(2)
        ]
        for pid in ("101", "102", "103", "104", "105")
    }

    a = select_subset(cycles_by_patient, max_patients=2, seed=42)
    b = select_subset(cycles_by_patient, max_patients=2, seed=42)

    assert a == b
    assert {c.patient_id for c in a} <= set(cycles_by_patient)
    assert len({c.patient_id for c in a}) == 2


def _ciclo_fake(patient_id: str, idx: int):
    from pipelines.audio.models import RespiratoryCycle

    return RespiratoryCycle(
        record_id=f"{patient_id}_1b1_Al_sc_Meditron",
        patient_id=patient_id,
        cycle_index=idx,
        start_s=float(idx),
        end_s=float(idx + 1),
        wav_path=Path(f"{patient_id}.wav"),
        label="normal",
    )


@pytest.mark.integration
def test_dataset_real_bate_com_as_contagens_medidas():
    if not _ICBHI_DIR.is_dir():
        pytest.skip(f"dataset ICBHI ausente em {_ICBHI_DIR} — rode `make data`")

    cycles, falhas = load_dataset(_ICBHI_DIR)

    n_arquivos_validos = len({c.record_id for c in cycles})
    n_pacientes = len({c.patient_id for c in cycles})

    assert n_arquivos_validos == 920
    assert n_pacientes == 126
    assert len(cycles) == 6898
    assert falhas == []
