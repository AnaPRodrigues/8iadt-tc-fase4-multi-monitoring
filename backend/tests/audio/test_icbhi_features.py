"""Testes da extração de features espectrais/MFCC por ciclo."""

from pathlib import Path

import numpy as np
import soundfile as sf

from pipelines.audio.icbhi_features import extract
from pipelines.audio.models import RespiratoryCycle

SR_ARQUIVO = 8000


def _wav_tom(path: Path, seconds: float, sr: int = SR_ARQUIVO, freq: float = 220.0) -> None:
    t = np.linspace(0, seconds, int(seconds * sr), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    sf.write(str(path), y, sr)


def _ciclo(wav_path: Path, start_s: float, end_s: float) -> RespiratoryCycle:
    return RespiratoryCycle(
        record_id=wav_path.stem,
        patient_id="101",
        cycle_index=0,
        start_s=start_s,
        end_s=end_s,
        wav_path=wav_path,
        label="normal",
    )


def test_vetor_tem_tamanho_fixo_para_duracoes_diferentes(tmp_path):
    wav = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    _wav_tom(wav, seconds=6.0)

    curto = extract(_ciclo(wav, 0.0, 1.0))
    longo = extract(_ciclo(wav, 0.0, 5.0))

    assert curto.shape == longo.shape
    assert curto.ndim == 1


def test_mesmo_ciclo_processado_duas_vezes_produz_o_mesmo_vetor(tmp_path):
    wav = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    _wav_tom(wav, seconds=3.0)
    cycle = _ciclo(wav, 0.5, 2.5)

    a = extract(cycle)
    b = extract(cycle)

    assert np.array_equal(a, b)


def test_ciclo_silencioso_nao_levanta_excecao_e_produz_vetor_finito(tmp_path):
    wav = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    sf.write(str(wav), np.zeros(int(2.0 * SR_ARQUIVO)), SR_ARQUIVO)
    cycle = _ciclo(wav, 0.0, 2.0)

    vetor = extract(cycle)

    assert vetor.size > 0
    assert np.isfinite(vetor).all()
