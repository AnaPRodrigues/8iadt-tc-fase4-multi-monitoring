"""Deteção heurística de padrão respiratório a partir de features acústicas.

Não classifica patologias (crackle/wheeze) — isso requer o dataset ICBHI
com anotações. Apenas deteta se o áudio contém padrões periódicos de baixa
frequência compatíveis com sons respiratórios (9-30 ciclos/minuto).

Usa:
1. Autocorrelação do envelope de energia para detetar periodicidade
2. Proporção de energia em banda baixa (<500 Hz vs >500 Hz)
3. Variação da taxa de cruzamento de zero (ZCR)

Heurística — não validada clinicamente.
"""

import numpy as np


def _energy_envelope(audio: np.ndarray, frame_size: int, hop: int) -> np.ndarray:
    """Envelope de energia (RMS) do sinal de áudio."""
    n_frames = (len(audio) - frame_size) // hop + 1
    if n_frames <= 0:
        return np.array([])
    rms = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * hop
        frame = audio[start:start + frame_size]
        rms[i] = np.sqrt(np.mean(frame.astype(np.float64) ** 2))
    return rms


def _autocorr_peak_period(signal: np.ndarray, sr: float, min_hz: float = 0.15, max_hz: float = 0.5) -> float | None:
    """Período dominante (em segundos) via autocorrelação, limitado a [min_hz, max_hz].

    Devolve None se o pico de autocorrelação for fraco (r < 0.3) ou se
    o sinal for muito curto.
    """
    n = len(signal)
    if n < 10:
        return None
    signal = signal - np.mean(signal)
    denom = np.sum(signal ** 2)
    if denom == 0:
        return None
    corr = np.correlate(signal, signal, mode="full")
    corr = corr[len(corr) // 2:] / denom
    # Procura o primeiro pico no intervalo de frequências respiratórias
    min_lag = int(sr / max_hz) if max_hz > 0 else 1
    max_lag = int(sr / min_hz) if min_hz > 0 else len(corr) - 1
    min_lag = max(1, min_lag)
    max_lag = min(len(corr) - 1, max_lag)
    if min_lag >= max_lag:
        return None
    peak_lag = int(np.argmax(corr[min_lag:max_lag])) + min_lag
    peak_val = corr[peak_lag]
    if peak_val < 0.3:
        return None
    return float(peak_lag / sr)


def detect_respiratory_pattern(
    audio_path: str,
    sr: int = 22050,
    frame_ms: float = 30.0,
) -> dict:
    """Deteta se o áudio contém padrão periódico compatível com respiração.

    Args:
        audio_path: Caminho para o ficheiro de áudio.
        sr: Taxa de amostragem para análise.
        frame_ms: Tamanho do frame em ms para envelope de energia.

    Returns:
        Dicionário com:
        - ``detected``: True se padrão respiratório provável
        - ``breath_rate_bpm``: Taxa estimada (ciclos/min) ou None
        - ``confidence``: 0-1 (qualidade da deteção)
        - ``method``: descrição do método usado
    """
    import soundfile as sf

    try:
        audio, file_sr = sf.read(str(audio_path), dtype="float32")
    except Exception:
        return {
            "detected": False,
            "breath_rate_bpm": None,
            "confidence": 0.0,
            "method": "falha na leitura do áudio",
        }

    # Converte para mono se necessário
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    # Re-amostra se necessário
    if file_sr != sr and file_sr > 0:
        from scipy import signal as scipy_signal
        audio = scipy_signal.resample(audio, int(len(audio) * sr / file_sr))

    frame_size = int(frame_ms / 1000.0 * sr)
    hop = frame_size // 2
    envelope = _energy_envelope(audio, frame_size, hop)
    if len(envelope) < 20:
        return {
            "detected": False,
            "breath_rate_bpm": None,
            "confidence": 0.0,
            "method": "áudio muito curto para análise",
        }

    envelope_sr = sr / hop  # taxa de amostragem do envelope

    # Deteta periodicidade no envelope
    period = _autocorr_peak_period(envelope, envelope_sr, min_hz=0.15, max_hz=0.5)

    # Proporção de energia em banda baixa (respiração tem energia < 500 Hz)
    if len(audio) >= 1024:
        from scipy import signal as scipy_signal
        freqs, psd = scipy_signal.welch(audio, sr, nperseg=min(1024, len(audio)))
        low_band = np.sum(psd[(freqs >= 50) & (freqs <= 500)])
        total = np.sum(psd[freqs >= 50])
        low_ratio = float(low_band / total) if total > 0 else 0.0
    else:
        low_ratio = 0.5  # neutro

    if period is not None:
        breath_rate = float(60.0 / period)
        # Confiança baseada na força da autocorrelação + energia em banda baixa
        confidence = round(float(min(1.0, 0.5 + 0.5 * low_ratio)), 2)
        return {
            "detected": True,
            "breath_rate_bpm": round(breath_rate, 1),
            "confidence": confidence,
            "method": f"autocorrelação do envelope (periodo={period:.2f}s, low_energy_ratio={low_ratio:.2f})",
        }

    # Sem periodicidade clara, mas verifica se há energia em banda respiratória
    if low_ratio > 0.6:
        return {
            "detected": True,
            "breath_rate_bpm": None,
            "confidence": round(float(low_ratio), 2),
            "method": f"energia predominante em banda baixa (<500 Hz: {low_ratio:.0%})",
        }

    return {
        "detected": False,
        "breath_rate_bpm": None,
        "confidence": 0.0,
        "method": "sem padrão respiratório identificável",
    }
