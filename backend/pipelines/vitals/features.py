"""Extração de features por janela.

Além das estatísticas brutas, extrai features de domínio de cardiotocografia
(baseline, variabilidade de curto prazo, decelerações). Esse é o ponto que mitiga o
risco central registrado no design: z-score e IsolationForest encontram outliers
estatísticos, mas o rótulo (pH) mede acidose fetal. São as features clínicas que dão
alguma chance de as duas coisas se correlacionarem.
"""

from dataclasses import dataclass

import numpy as np

from pipelines.vitals.windowing import Window

# Convenção clínica (NICHD) para deceleração: queda de pelo menos 15 bpm abaixo do
# baseline sustentada por pelo menos 15 segundos.
DECEL_DROP_BPM = 15.0
DECEL_MIN_S = 15.0


@dataclass(frozen=True)
class FeatureVector:
    mean: float
    std: float
    min: float
    max: float
    baseline: float
    short_term_variability: float
    deceleration_count: float
    valid: bool

    def to_array(self) -> list[float]:
        return [
            self.mean,
            self.std,
            self.min,
            self.max,
            self.baseline,
            self.short_term_variability,
            self.deceleration_count,
        ]


_NAN = float("nan")
_INVALIDO = FeatureVector(_NAN, _NAN, _NAN, _NAN, _NAN, _NAN, _NAN, valid=False)


def _conta_deceleracoes(fhr: np.ndarray, baseline: float, fs: float) -> int:
    """Conta episódios contíguos abaixo de ``baseline - DECEL_DROP_BPM``."""
    min_amostras = int(DECEL_MIN_S * fs)
    abaixo = fhr < (baseline - DECEL_DROP_BPM)

    total = 0
    corrida = 0
    for flag in abaixo:
        if flag:
            corrida += 1
            continue
        if corrida >= min_amostras:
            total += 1
        corrida = 0
    if corrida >= min_amostras:
        total += 1
    return total


def extract(window: Window, fs: float) -> FeatureVector:
    """Extrai o vetor de features de uma janela.

    Janela marcada ``insufficient_data`` devolve NaN com ``valid=False``. NaN é
    deliberado: se o chamador ignorar a flag, o modelo falha alto em vez de ser
    silenciosamente contaminado por zeros que parecem dados reais.
    """
    if window.insufficient_data or window.fhr.size == 0:
        return _INVALIDO

    fhr = np.asarray(window.fhr, dtype=float)
    baseline = float(np.median(fhr))
    diffs = np.abs(np.diff(fhr))

    return FeatureVector(
        mean=float(np.mean(fhr)),
        std=float(np.std(fhr)),
        min=float(np.min(fhr)),
        max=float(np.max(fhr)),
        baseline=baseline,
        short_term_variability=float(np.mean(diffs)) if diffs.size else 0.0,
        deceleration_count=float(_conta_deceleracoes(fhr, baseline, fs)),
        valid=True,
    )
