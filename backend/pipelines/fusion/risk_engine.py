"""Reordenação cronológica cross-modal e cálculo do risk score ponderado por janela de
tempo, com decaimento temporal (FUSION-02, FUSION-03, FUSION-04, FUSION-14).

Eventos de modalidades diferentes podem chegar fora de ordem cronológica -- `sort_events`
normaliza a lista antes de qualquer varredura por janela, para que o motor sempre
processe a timeline em ordem crescente.
"""

from pipelines.fusion.models import FusionEvent


def sort_events(events: list[FusionEvent]) -> list[FusionEvent]:
    """Reordena os eventos por `demo_timestamp_s`, crescente (FUSION-02)."""
    return sorted(events, key=lambda e: e.demo_timestamp_s)


def decay(elapsed_s: float, half_life_s: float) -> float:
    """Decaimento exponencial: `2 ** (-elapsed_s / half_life_s)`.

    `1.0` em `elapsed_s=0`, cai pela metade a cada `half_life_s` decorridos --
    monotonicamente decrescente conforme `elapsed_s` cresce.
    """
    return 2 ** (-elapsed_s / half_life_s)
