"""Features acústicas para o score de fadiga vocal.

Receita Parselmouth/Praat validada em sessão de design contra sinal sintético
(valores plausíveis: jitter≈0.3%, shimmer≈1.8%, HNR≈19.6 dB) — ``jitter_local``/
``shimmer_local`` são as frações brutas devolvidas pelo Praat (ex.: ``0.003`` =
0.3%), sem conversão de unidade.
"""

import math
from pathlib import Path

import librosa
import numpy as np
import parselmouth
from parselmouth.praat import call

from pipelines.audio.models import AcousticFeatures, Transcript

_SILENCE_TOP_DB = 30.0


def _finite_or_zero(value: float) -> float:
    value = float(value)
    return value if math.isfinite(value) else 0.0


def extract(audio_path: Path, transcript: Transcript) -> AcousticFeatures:
    """Jitter, shimmer, HNR (Parselmouth/Praat) + taxa de pausas e velocidade de fala."""
    audio_path = Path(audio_path)

    snd = parselmouth.Sound(str(audio_path))
    pitch = call(snd, "To Pitch", 0.0, 75, 500)
    pp = call(snd, "To PointProcess (periodic, cc)", 75, 500)
    jitter_local = call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    shimmer_local = call([snd, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
    hnr = call(harmonicity, "Get mean", 0, 0)
    del pitch  # calculada apenas como pré-requisito do PointProcess acima

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    duration_s = len(y) / sr if sr else 0.0

    if y.size > 0 and duration_s > 0:
        intervals = librosa.effects.split(y, top_db=_SILENCE_TOP_DB)
        speech_duration_s = float(np.sum(intervals[:, 1] - intervals[:, 0])) / sr
    else:
        speech_duration_s = 0.0

    pause_rate = (
        max(duration_s - speech_duration_s, 0.0) / duration_s if duration_s > 0 else 0.0
    )

    n_words = len(transcript.text.split())
    speaking_rate_wps = n_words / speech_duration_s if speech_duration_s > 0 else 0.0

    return AcousticFeatures(
        jitter_local=_finite_or_zero(jitter_local),
        shimmer_local=_finite_or_zero(shimmer_local),
        hnr_db=_finite_or_zero(hnr),
        pause_rate=_finite_or_zero(pause_rate),
        speaking_rate_wps=_finite_or_zero(speaking_rate_wps),
    )
