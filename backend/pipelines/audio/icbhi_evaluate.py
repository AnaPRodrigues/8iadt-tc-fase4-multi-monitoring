"""Avaliação do classificador respiratório contra o rótulo real do ICBHI (AUDIO-04).

Sem wrapper de relatório agregado (diferente de ``pipelines/vitals/evaluate.py``):
aqui não há prevalência relevante o suficiente para justificar um tipo novo
(design.md § Components — YAGNI).
"""

import json
from dataclasses import asdict
from pathlib import Path

from common.metrics import MetricsReport, binary_metrics


def evaluate(
    y_true: list[str], y_pred: list[str], classes: tuple[str, ...]
) -> list[MetricsReport]:
    """Precision/recall/F1 por classe, one-vs-rest, via ``common.metrics.binary_metrics``."""
    reports: list[MetricsReport] = []
    for classe in classes:
        true_bin = [t == classe for t in y_true]
        pred_bin = [p == classe for p in y_pred]
        reports.append(binary_metrics(true_bin, pred_bin, detector=classe))
    return reports


def save_evaluation(reports: list[MetricsReport], path: Path) -> None:
    """Grava a lista de relatórios como JSON, criando os diretórios necessários."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(r) for r in reports], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
