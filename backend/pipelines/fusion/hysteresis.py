"""Classificador de nível (verde/amarelo/vermelho) com histerese e memória de estado
entre janelas.

`HysteresisClassifier` mantém o nível atual internamente; `.update(score)` só muda de
nível quando o score cruza `limiar + histerese` (subindo) ou `limiar - histerese`
(descendo) a partir do nível atual -- nunca reavalia do zero a cada chamada. É
exatamente isso que impede a oscilação na fronteira entre níveis e mantém o último
nível quando não há sinal novo suficiente para cruzar a banda.
"""

VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"


class HysteresisClassifier:
    """Classifica scores em verde/amarelo/vermelho com banda de histerese em torno dos
    limiares configurados, mantendo o nível anterior como referência a cada chamada."""

    def __init__(
        self,
        threshold_amarelo: float,
        threshold_vermelho: float,
        hysteresis: float,
        initial_level: str = VERDE,
    ) -> None:
        self._threshold_amarelo = threshold_amarelo
        self._threshold_vermelho = threshold_vermelho
        self._hysteresis = hysteresis
        self._level = initial_level

    @property
    def level(self) -> str:
        """Nível atual, sem reavaliar -- reflete a última chamada a `update`."""
        return self._level

    def update(self, score: float) -> str:
        """Atualiza e devolve o nível a partir do score, aplicando a banda de histerese
        relativa ao nível atual (não a um recálculo absoluto do zero)."""
        if self._level == VERDE:
            if score > self._threshold_vermelho + self._hysteresis:
                self._level = VERMELHO
            elif score > self._threshold_amarelo + self._hysteresis:
                self._level = AMARELO
        elif self._level == AMARELO:
            if score > self._threshold_vermelho + self._hysteresis:
                self._level = VERMELHO
            elif score < self._threshold_amarelo - self._hysteresis:
                self._level = VERDE
        elif self._level == VERMELHO:
            if score < self._threshold_amarelo - self._hysteresis:
                self._level = VERDE
            elif score < self._threshold_vermelho - self._hysteresis:
                self._level = AMARELO

        return self._level
