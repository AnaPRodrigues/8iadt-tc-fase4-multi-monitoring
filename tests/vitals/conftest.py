"""Fixtures WFDB sintéticas — permitem testar sem baixar os GB do CTU-UHB.

O formato replica o real verificado: 4 Hz, sinais FHR e UC, pH em comentário.
"""

import numpy as np
import pytest
import wfdb

FS = 4


def escreve_registro(
    directory,
    record_name: str,
    *,
    ph: float | None = 7.26,
    n_amostras: int = 240,
    sig_name: tuple[str, ...] = ("FHR", "UC"),
) -> str:
    """Escreve um par .hea/.dat válido e devolve o caminho sem extensão."""
    rng = np.random.default_rng(0)
    n_sig = len(sig_name)
    sinal = np.column_stack(
        [rng.normal(140.0, 5.0, n_amostras) for _ in range(n_sig)]
    ).astype(float)

    comments = ["-- Outcome measures"]
    if ph is not None:
        comments.append(f"pH           {ph}")
    comments.append("Apgar1       8")

    wfdb.wrsamp(
        record_name,
        fs=FS,
        units=["bpm", "nd"][:n_sig],
        sig_name=list(sig_name),
        p_signal=sinal,
        fmt=["16"] * n_sig,
        comments=comments,
        write_dir=str(directory),
    )
    return str(directory / record_name)


@pytest.fixture
def registro_valido(tmp_path):
    return escreve_registro(tmp_path, "0001", ph=7.26)


@pytest.fixture
def registro_patologico(tmp_path):
    return escreve_registro(tmp_path, "0002", ph=7.01)
