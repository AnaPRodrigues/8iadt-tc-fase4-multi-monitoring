"""Sentimento local (positivo/negativo/neutro) via léxico pt-BR embutido (AUDIO-08).

100% local (AD-002/AD-003): nenhuma chamada a serviço de nuvem — o léxico é uma
constante do módulo, sem I/O de rede.
"""

import re

from pipelines.audio.critical_terms import normalize_text
from pipelines.audio.models import SentimentResult

_WORD_RE = re.compile(r"[a-z]+")

_POSITIVE_WORDS = {
    "bem",
    "otimo",
    "otima",
    "melhor",
    "melhorando",
    "tranquilo",
    "tranquila",
    "aliviado",
    "aliviada",
    "feliz",
    "calmo",
    "calma",
    "confortavel",
    "bom",
    "boa",
}

_NEGATIVE_WORDS = {
    "mal",
    "pior",
    "piorando",
    "dor",
    "ruim",
    "preocupado",
    "preocupada",
    "cansado",
    "cansada",
    "triste",
    "assustado",
    "assustada",
    "sofrendo",
    "grave",
    "forte",
}


def classify(transcript_text: str, threshold: float) -> SentimentResult:
    """Sentimento por contagem de ocorrências normalizadas do léxico embutido.

    ``score = (pos - neg) / (pos + neg)`` quando há ao menos um hit, senão
    ``0.0``. ``|score| < threshold`` classifica como ``"neutro"``.
    """
    words = _WORD_RE.findall(normalize_text(transcript_text))
    pos = sum(1 for w in words if w in _POSITIVE_WORDS)
    neg = sum(1 for w in words if w in _NEGATIVE_WORDS)

    if pos + neg == 0:
        return SentimentResult(label="neutro", score=0.0)

    score = (pos - neg) / (pos + neg)
    if abs(score) < threshold:
        label = "neutro"
    elif score > 0:
        label = "positivo"
    else:
        label = "negativo"

    return SentimentResult(label=label, score=score)
