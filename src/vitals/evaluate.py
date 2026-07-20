"""Comparação dos veredictos por registro contra o rótulo pH real.

SPEC_DEVIATION: o design assinava ``evaluate(verdicts, records) -> list[MetricsReport]``.
O retorno é um ``EvaluationReport`` que embrulha os relatórios por detector e acrescenta
a prevalência. Prevalência descreve o conjunto avaliado, não o desempenho de um detector:
colocá-la dentro de cada ``MetricsReport`` a duplicaria em todos eles.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from core.logging import get_logger
from core.metrics import MetricsReport, binary_metrics
from vitals.aggregate import RecordVerdict
from vitals.loader import VitalRecord, is_pathological

log = get_logger("vitals.evaluate")


@dataclass(frozen=True)
class EvaluationReport:
    prevalence: float | None
    n_records: int
    n_pathological: int
    n_excluded: int
    metrics: list[MetricsReport]


def evaluate(
    verdicts_by_detector: dict[str, list[RecordVerdict]],
    records: list[VitalRecord],
) -> EvaluationReport:
    """Calcula precision/recall/F1 por detector contra o rótulo pH.

    Veredictos indeterminados (registro sem nenhuma janela válida) são excluídos:
    não há evidência para contá-los como acerto nem como erro.
    """
    rotulo = {r.record_id: is_pathological(r.ph) for r in records}
    n_patologicos = sum(rotulo.values())
    prevalencia = n_patologicos / len(records) if records else None

    if records and n_patologicos == 0:
        log.warning(
            "nenhum registro patológico no subconjunto (%d registros): o recall fica "
            "indefinido e a demo de detecção positiva não está garantida",
            len(records),
        )

    metricas: list[MetricsReport] = []
    n_excluidos = 0

    for nome, verdicts in verdicts_by_detector.items():
        y_true: list[bool] = []
        y_pred: list[bool] = []

        for v in verdicts:
            if v.record_id not in rotulo:
                continue
            if v.predicted_pathological is None:
                n_excluidos += 1
                continue
            y_true.append(rotulo[v.record_id])
            y_pred.append(v.predicted_pathological)

        metricas.append(binary_metrics(y_true, y_pred, detector=nome))

    return EvaluationReport(
        prevalence=prevalencia,
        n_records=len(records),
        n_pathological=n_patologicos,
        n_excluded=n_excluidos,
        metrics=metricas,
    )


def save_evaluation(report: EvaluationReport, path: Path) -> None:
    """Grava o relatório completo (prevalência + métricas por detector) como JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
