"""Testes de features acústicas (AUDIO-11)."""

import math
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from pipelines.audio.acoustic_features import extract
from pipelines.audio.models import Transcript

SR = 16000


def _voice(path: Path, seconds: float = 2.0, silence_at: list[tuple[float, float]] | None = None):
    """Sinal harmônico (fundamental + 2 sobretons) + ruído leve — mesmo tipo validado no design."""
    rng = np.random.default_rng(0)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    wobble = 1.0 + 0.002 * np.sin(2 * np.pi * 3 * t)
    phase = 2 * np.pi * 150.0 * np.cumsum(wobble) / SR
    y = 0.6 * np.sin(phase) + 0.2 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
    y += 0.01 * rng.standard_normal(n)

    if silence_at:
        for s, e in silence_at:
            si, ei = int(s * SR), int(e * SR)
            y[si:ei] = 0.0005 * rng.standard_normal(ei - si)

    sf.write(str(path), y.astype(np.float32), SR)


def _transcript(audio_path: Path, text: str) -> Transcript:
    return Transcript(audio_path=audio_path, text=text, segments=[], reliable=True)


def test_features_de_sinal_de_voz_sintetico_sao_finitas_e_plausiveis(tmp_path):
    wav = tmp_path / "voz.wav"
    _voice(wav)

    features = extract(wav, _transcript(wav, "um dois tres"))

    assert math.isfinite(features.jitter_local)
    assert math.isfinite(features.shimmer_local)
    assert math.isfinite(features.hnr_db)
    assert 0.0 <= features.jitter_local < 0.05  # jitter < 5%
    assert 0.0 <= features.shimmer_local < 0.20  # shimmer < 20%
    assert 0.0 <= features.hnr_db <= 40.0  # HNR entre 0 e 40 dB


def test_sinal_com_pausas_inseridas_produz_pause_rate_maior_que_sem_pausas(tmp_path):
    wav_continuo = tmp_path / "continuo.wav"
    _voice(wav_continuo)
    wav_com_pausas = tmp_path / "com_pausas.wav"
    _voice(wav_com_pausas, silence_at=[(0.5, 1.2)])

    sem_pausas = extract(wav_continuo, _transcript(wav_continuo, "um dois tres"))
    com_pausas = extract(wav_com_pausas, _transcript(wav_com_pausas, "um dois tres"))

    assert com_pausas.pause_rate > sem_pausas.pause_rate


def test_speaking_rate_wps_e_calculado_a_partir_da_contagem_de_palavras_do_transcript(tmp_path):
    """Dobrar a contagem de palavras do transcript (mesmo áudio) dobra a taxa — prova que usa
    o transcript passado, não recalcula transcrição própria."""
    wav = tmp_path / "voz.wav"
    _voice(wav)

    tres_palavras = extract(wav, _transcript(wav, "um dois tres"))
    seis_palavras = extract(wav, _transcript(wav, "um dois tres quatro cinco seis"))

    assert seis_palavras.speaking_rate_wps > 0.0
    assert seis_palavras.speaking_rate_wps == pytest.approx(2 * tres_palavras.speaking_rate_wps)
