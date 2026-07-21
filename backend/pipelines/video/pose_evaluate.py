"""Precision/recall/F1 da raia pose contra o rótulo real do URFD (VIDEO-04).

Persistência do relatório reaproveita `common.metrics.save_report` diretamente
-- não há necessidade de um wrapper local de uma linha só para isso.
"""

from common.logging import get_logger
from common.metrics import MetricsReport, binary_metrics
from pipelines.video.models import SequenceVerdict

log = get_logger("video.pose_evaluate")


def evaluate(verdicts: list[SequenceVerdict]) -> MetricsReport:
    """Compara `predicted` ("queda") contra `label` ("fall"), mapeamento explícito.

    Veredictos "dados_insuficientes" são excluídos do cálculo -- não contam
    como TP/FP/FN (mesmo princípio de VITALS-10/PRESC-14: indefinido != zero).
    """
    excluidos = [v for v in verdicts if v.predicted == "dados_insuficientes"]
    if excluidos:
        log.warning(
            "%d veredito(s) 'dados_insuficientes' excluído(s) do cálculo de %d",
            len(excluidos),
            len(verdicts),
        )

    considerados = [v for v in verdicts if v.predicted != "dados_insuficientes"]
    y_true = [v.label == "fall" for v in considerados]
    y_pred = [v.predicted == "queda" for v in considerados]

    return binary_metrics(y_true, y_pred, detector="pose_fall")
