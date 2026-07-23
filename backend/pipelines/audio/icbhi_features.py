"""Extração de features espectrais/MFCC por ciclo respiratório.

Ciclos têm duração variável; agregar média+desvio-padrão ao longo dos frames
produz um vetor 1-D de tamanho fixo, exigido pelo classificador (icbhi_classifier.py).
"""

import librosa
import numpy as np

from pipelines.audio.models import RespiratoryCycle

N_MFCC = 13


def extract(cycle: RespiratoryCycle, sr: int = 4000) -> np.ndarray:
    """Recorta ``[start_s, end_s]`` do WAV do ciclo e extrai o vetor de features.

    MFCC(13) + centroide/bandwidth/rolloff espectral + zero-crossing rate,
    resample para ``sr``, agregados por média+desvio-padrão ao longo dos frames.
    """
    duracao = max(cycle.end_s - cycle.start_s, 0.0)
    y, _ = librosa.load(
        str(cycle.wav_path), sr=sr, offset=cycle.start_s, duration=duracao, mono=True
    )
    if y.size == 0:
        y = np.zeros(1, dtype=float)

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y=y)

    frames = np.vstack([mfcc, centroid, bandwidth, rolloff, zcr])
    vetor = np.concatenate([frames.mean(axis=1), frames.std(axis=1)])
    return np.nan_to_num(vetor, nan=0.0, posinf=0.0, neginf=0.0).astype(float)
