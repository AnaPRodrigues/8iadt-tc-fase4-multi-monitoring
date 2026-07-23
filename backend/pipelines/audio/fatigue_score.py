"""Score heurístico de fadiga/qualidade vocal.

Heurística relativa, não validada clinicamente: z-score de cada feature contra
o ``baseline`` da própria execução, combinados
em média simples de ``[jitter_z, shimmer_z, -hnr_z, pause_rate_z, -speaking_rate_z]``
(sinal invertido em HNR e velocidade de fala: "quanto maior, melhor").
"""

from statistics import mean, pstdev

from pipelines.audio.models import AcousticFeatures


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
