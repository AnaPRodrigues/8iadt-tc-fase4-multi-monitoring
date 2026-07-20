"""Fatiamento da série em janelas deslizantes.

SPEC_DEVIATION: o design assinava ``make_windows(record, size_s, stride_s)``. A máscara
de validade produzida por ``preprocess`` precisa entrar aqui — sem ela não há como
marcar ``insufficient_data`` (VITALS-09), que é justamente o que impede uma janela
degradada de virar falso negativo silencioso na agregação.
"""

from dataclasses import dataclass

import numpy as np

from pipelines.vitals.loader import VitalRecord


@dataclass(frozen=True)
class Window:
    record_id: str
    start_s: float
    end_s: float
    fhr: np.ndarray
    uc: np.ndarray
    insufficient_data: bool


def make_windows(
    record: VitalRecord,
    size_s: float,
    stride_s: float,
    mask: np.ndarray,
    max_invalid_fraction: float = 0.5,
) -> list[Window]:
    """Gera janelas completas em ordem cronológica estritamente crescente.

    A janela final incompleta é descartada: uma janela mais curta teria suporte
    amostral diferente das demais e distorceria a comparação entre elas.
    """
    if size_s <= 0 or stride_s <= 0:
        raise ValueError("size_s e stride_s precisam ser positivos")

    n_janela = int(size_s * record.fs)
    n_passo = int(stride_s * record.fs)
    total = len(record.fhr)

    janelas: list[Window] = []
    for inicio in range(0, total - n_janela + 1, n_passo):
        fim = inicio + n_janela
        fracao_invalida = float(np.mean(mask[inicio:fim])) if n_janela else 1.0
        janelas.append(
            Window(
                record_id=record.record_id,
                start_s=inicio / record.fs,
                end_s=fim / record.fs,
                fhr=record.fhr[inicio:fim],
                uc=record.uc[inicio:fim],
                insufficient_data=fracao_invalida > max_invalid_fraction,
            )
        )
    return janelas
