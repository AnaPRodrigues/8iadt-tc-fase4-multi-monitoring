"""Detectores de anomalia por janela.

SPEC_DEVIATION: o design assinava ``score(windows) -> list[float]``. O retorno é
``list[float | None]``: janela sem dado utilizável recebe ``None``, nunca ``0.0``.
Zero é um score legítimo (valor exatamente no baseline) — usá-lo para "sem dado"
tornaria as duas situações indistinguíveis na agregação.
"""

import math
from typing import Protocol, runtime_checkable

import numpy as np
from sklearn.ensemble import IsolationForest

from core.logging import get_logger
from vitals.features import FeatureVector

log = get_logger("vitals.detectors")

# Abaixo disso o IsolationForest treina, mas o resultado não tem significado
# estatístico — melhor reportar "dados insuficientes" do que devolver um score
# arbitrário que o relatório trataria como medida.
MIN_TRAIN_SAMPLES = 10


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


class IsolationForestDetector:
    """Detector multivariado sobre o vetor de features completo (VITALS-04).

    ``seed`` é obrigatória e fixa ``random_state``: sem isso o mesmo dataset
    produziria métricas diferentes a cada execução e o relatório não seria
    reprodutível.
    """

    name = "isolation_forest"

    def __init__(self, contamination: float, seed: int) -> None:
        if not 0 < contamination <= 0.5:
            raise ValueError("contamination precisa estar em (0, 0.5]")
        self.contamination = contamination
        self.seed = seed
        self.n_treino = 0
        self.insufficient_data = False

    def _ajusta(self, features: list[FeatureVector]) -> IsolationForest | None:
        validos = [f for f in features if f.valid]
        self.n_treino = len(validos)

        if len(validos) < MIN_TRAIN_SAMPLES:
            self.insufficient_data = True
            if features:
                log.warning(
                    "dados insuficientes para o IsolationForest: %d janela(s) válida(s), "
                    "mínimo %d — scores não serão produzidos",
                    len(validos),
                    MIN_TRAIN_SAMPLES,
                )
            return None

        self.insufficient_data = False
        modelo = IsolationForest(contamination=self.contamination, random_state=self.seed)
        modelo.fit(np.array([f.to_array() for f in validos], dtype=float))
        return modelo

    def score(self, features: list[FeatureVector]) -> list[float | None]:
        modelo = self._ajusta(features)
        if modelo is None:
            return [None] * len(features)

        # score_samples: quanto MENOR, mais anômalo. Negado para ficar coerente
        # com o z-score, onde maior = mais anômalo.
        return [
            None if not f.valid else -float(modelo.score_samples([f.to_array()])[0])
            for f in features
        ]

    def flag(self, features: list[FeatureVector]) -> list[bool | None]:
        modelo = self._ajusta(features)
        if modelo is None:
            return [None] * len(features)

        return [
            None if not f.valid else bool(modelo.predict([f.to_array()])[0] == -1)
            for f in features
        ]
