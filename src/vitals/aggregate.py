"""Agregação dos veredictos de janela em um veredicto por registro (AD-027).

O rótulo (pH) é um por registro; os detectores produzem centenas de veredictos por
janela. Esta regra é a ponte entre os dois — e, por isso, determina sozinha as
métricas de precision/recall reportadas no relatório.

A alternativa ingênua ("qualquer janela anômala ⇒ registro patológico") foi rejeitada
no design: em séries de ~21.600 amostras quase todo registro tem algum outlier, o que
levaria a recall ≈ 1.0 e precision ≈ prevalência — uma métrica sem poder discriminativo.
"""

from dataclasses import dataclass

DEFAULT_TAU = 0.15


@dataclass(frozen=True)
class RecordVerdict:
    record_id: str
    predicted_pathological: bool | None
    anomalous_fraction: float | None
    n_windows_valid: int
    n_windows_excluded: int


def aggregate(
    record_id: str, window_flags: list[bool | None], tau: float = DEFAULT_TAU
) -> RecordVerdict:
    """Classifica o registro pela fração de janelas anômalas entre as válidas.

    Janelas ``None`` (dados insuficientes) são excluídas do denominador — contá-las
    como normais diluiria a fração e esconderia registros cuja maior parte do sinal
    foi perdida. Um registro sem nenhuma janela válida fica ``None`` (indeterminado),
    nunca "normal": não há evidência para afirmar qualquer das duas coisas.
    """
    if not 0 <= tau <= 1:
        raise ValueError(f"tau precisa estar em [0, 1], recebido: {tau}")

    validas = [f for f in window_flags if f is not None]
    n_excluidas = len(window_flags) - len(validas)

    if not validas:
        return RecordVerdict(
            record_id=record_id,
            predicted_pathological=None,
            anomalous_fraction=None,
            n_windows_valid=0,
            n_windows_excluded=n_excluidas,
        )

    fracao = sum(validas) / len(validas)
    return RecordVerdict(
        record_id=record_id,
        predicted_pathological=fracao > tau,
        anomalous_fraction=fracao,
        n_windows_valid=len(validas),
        n_windows_excluded=n_excluidas,
    )
