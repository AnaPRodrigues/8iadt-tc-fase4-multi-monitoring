"""Relatório de precision/recall/F1 compartilhado pelas features.

Métricas indefinidas são representadas como ``None``, nunca como ``0.0``: um recall
indefinido (nenhum positivo real no conjunto) é uma informação diferente de um recall
zero (havia positivos e nenhum foi encontrado). Confundir os dois esconderia justamente
os casos em que não há evidência suficiente para calcular a métrica.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetricsReport:
    detector: str
    precision: float | None
    recall: float | None
    f1: float | None
    support: int


def binary_metrics(
    y_true: list[bool], y_pred: list[bool], detector: str
) -> MetricsReport:
    """Calcula precision/recall/F1 de uma classificação binária.

    ``support`` é a quantidade de positivos reais. Retorna ``None`` para cada métrica
    cujo denominador é zero.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true e y_pred precisam ter o mesmo comprimento")

    tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t and not p)

    predicted_positives = tp + fp
    actual_positives = tp + fn

    precision = tp / predicted_positives if predicted_positives else None
    recall = tp / actual_positives if actual_positives else None

    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return MetricsReport(
        detector=detector,
        precision=precision,
        recall=recall,
        f1=f1,
        support=actual_positives,
    )


def save_report(report: MetricsReport, path: Path) -> None:
    """Grava o relatório como JSON indentado, criando os diretórios necessários."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
