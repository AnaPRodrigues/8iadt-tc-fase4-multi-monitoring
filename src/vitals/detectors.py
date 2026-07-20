"""Detectores de anomalia por janela.

SPEC_DEVIATION: o design assinava ``score(windows) -> list[float]``. O retorno é
``list[float | None]``: janela sem dado utilizável recebe ``None``, nunca ``0.0``.
Zero é um score legítimo (valor exatamente no baseline) — usá-lo para "sem dado"
tornaria as duas situações indistinguíveis na agregação.
"""

import math
from typing import Protocol, runtime_checkable

from vitals.features import FeatureVector


@runtime_checkable
class Detector(Protocol):
    name: str

    def score(self, features: list[FeatureVector]) -> list[float | None]: ...

    def flag(self, features: list[FeatureVector]) -> list[bool | None]: ...


class RollingZScoreDetector:
    """Baseline univariado sobre a média de FHR da janela (VITALS-03).

    O baseline é móvel: cada janela é comparada às ``baseline_size`` janelas válidas
    imediatamente anteriores. Janelas inválidas não entram no baseline — uma janela
    descartada por perda de sinal não pode contaminar a estatística de referência.
    """

    name = "zscore"

    def __init__(self, threshold: float, baseline_size: int = 20) -> None:
        if threshold <= 0:
            raise ValueError("threshold precisa ser positivo")
        if baseline_size < 2:
            raise ValueError("baseline_size precisa ser ao menos 2")
        self.threshold = threshold
        self.baseline_size = baseline_size

    def score(self, features: list[FeatureVector]) -> list[float | None]:
        scores: list[float | None] = []
        historico: list[float] = []

        for f in features:
            if not f.valid:
                scores.append(None)
                continue

            if len(historico) < self.baseline_size:
                scores.append(None)
            else:
                janela = historico[-self.baseline_size :]
                media = sum(janela) / len(janela)
                variancia = sum((v - media) ** 2 for v in janela) / len(janela)
                desvio = math.sqrt(variancia)
                if desvio == 0.0:
                    # Baseline sem variação: qualquer desvio é um outlier genuíno.
                    scores.append(0.0 if f.mean == media else math.inf)
                else:
                    scores.append(abs(f.mean - media) / desvio)

            historico.append(f.mean)

        return scores

    def flag(self, features: list[FeatureVector]) -> list[bool | None]:
        return [None if s is None else s > self.threshold for s in self.score(features)]
