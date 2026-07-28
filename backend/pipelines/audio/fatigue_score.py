"""Score heurístico de fadiga/qualidade vocal.

Duas estratégias complementares:

1. **Relativa (z-score)**: compara as features do áudio atual contra um
   ``baseline`` de áudios da mesma execução. Requer ≥2 áudios para ter
   desvio-padrão > 0. Com 1 único áudio, o z-score é sempre 0.0.

2. **Absoluta (thresholds)**: usada como fallback quando o baseline é
   insuficiente (<2 áudios). Usa thresholds de literatura (jitter > 1.04%,
   shimmer > 3.81%, HNR < 15 dB) adaptados para voz patológica.

Heurística relativa, não validada clinicamente.
"""

from statistics import mean, pstdev

from pipelines.audio.models import AcousticFeatures

# Thresholds absolutos para deteção de voz possivelmente fatigada/alterada.
# Baseados em valores de referência para voz normal vs. patológica:
# - Jitter > 1.04% (Teixeira et al., 2013)
# - Shimmer > 3.81% (Teixeira et al., 2013)
# - HNR < 15 dB (voz ruidosa / soprosa)
_JITTER_THRESHOLD = 0.0104   # 1.04%
_SHIMMER_THRESHOLD = 0.0381  # 3.81%
_HNR_THRESHOLD = 15.0        # dB


def _zscore(value: float, population: list[float]) -> float:
    """Z-score de ``value`` contra ``population``; desvio-padrão zero devolve 0.0 (sem NaN/erro)."""
    desvio = pstdev(population)
    if desvio == 0:
        return 0.0
    return (value - mean(population)) / desvio


def score(features: AcousticFeatures, baseline: list[AcousticFeatures]) -> float:
    """Média dos z-scores das 5 features, com HNR e velocidade de fala invertidos."""
    jitter_z = _zscore(features.jitter_local, [b.jitter_local for b in baseline])
    shimmer_z = _zscore(features.shimmer_local, [b.shimmer_local for b in baseline])
    hnr_z = _zscore(features.hnr_db, [b.hnr_db for b in baseline])
    pause_z = _zscore(features.pause_rate, [b.pause_rate for b in baseline])
    speaking_z = _zscore(features.speaking_rate_wps, [b.speaking_rate_wps for b in baseline])

    componentes = [jitter_z, shimmer_z, -hnr_z, pause_z, -speaking_z]
    return sum(componentes) / len(componentes)


def is_fatigued(score: float, threshold: float) -> bool:
    """``True`` quando o score heurístico ultrapassa o limiar configurado."""
    return score > threshold


def fatigue_absolute(features: AcousticFeatures) -> dict:
    """Avaliação por thresholds absolutos — independente de baseline.

    Devolve um dicionário com:
    - ``fatigued``: True se ≥2 indicadores excederem os thresholds
    - ``indicators``: lista de indicadores alterados
    - ``details``: valores medidos vs thresholds
    """
    indicators: list[str] = []
    details: dict[str, dict] = {}

    # Jitter (variação ciclo-a-ciclo na frequência fundamental)
    if features.jitter_local > _JITTER_THRESHOLD:
        indicators.append("jitter_elevado")
    details["jitter"] = {
        "value": round(features.jitter_local, 5),
        "threshold": _JITTER_THRESHOLD,
        "unit": "%",
    }

    # Shimmer (variação ciclo-a-ciclo na amplitude)
    if features.shimmer_local > _SHIMMER_THRESHOLD:
        indicators.append("shimmer_elevado")
    details["shimmer"] = {
        "value": round(features.shimmer_local, 5),
        "threshold": _SHIMMER_THRESHOLD,
        "unit": "%",
    }

    # HNR (Harmonics-to-Noise Ratio) — valores baixos = voz ruidosa
    if features.hnr_db < _HNR_THRESHOLD:
        indicators.append("hnr_reduzido")
    details["hnr"] = {
        "value": round(features.hnr_db, 1),
        "threshold": _HNR_THRESHOLD,
        "unit": "dB",
    }

    return {
        "fatigued": len(indicators) >= 2,
        "indicators": indicators,
        "details": details,
    }
