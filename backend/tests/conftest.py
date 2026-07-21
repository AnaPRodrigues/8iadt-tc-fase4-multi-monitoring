"""Fixtures WFDB sintéticas — permitem testar sem baixar os GB do CTU-UHB.

O formato replica o real verificado: 4 Hz, sinais FHR e UC, pH em comentário.
Fica na raiz de ``tests/`` para servir tanto os testes unitários quanto os de integração.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import numpy as np
import pytest
import wfdb

from aws import adapters


@pytest.fixture(autouse=True)
def _registro_de_adapters_limpo(monkeypatch):
    """Isola o registro de adapters AWS entre testes (evita vazamento de estado global)."""
    monkeypatch.setattr(adapters, "_TEXT_EXTRACTORS", {})
    monkeypatch.setattr(adapters, "_IMAGE_ANALYZERS", {})

FS = 4

# ---- Harness do script shell de aquisição (F0) — sem download real ----
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "download_datasets.sh"
_BASH = shutil.which("bash") or "/bin/bash"


def _mkexec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def stubbin(tmp_path):
    """Diretório de PATH com as ferramentas pedidas como stubs executáveis."""
    d = tmp_path / "bin"
    d.mkdir()

    def make(tools, bodies=None):
        bodies = bodies or {}
        for t in tools:
            _mkexec(d / t, bodies.get(t, "#!/usr/bin/env bash\nexit 0\n"))
        return d

    return make


@pytest.fixture
def run():
    """Roda `source script; <func_call>` e devolve o CompletedProcess.

    `path` substitui o PATH do filho (simula ferramentas presentes/ausentes);
    `cwd` default é a raiz do repo para resolver `.venv`.
    """

    def _run(func_call, path=None, env=None, cwd=_REPO_ROOT):
        full = os.environ.copy()
        if env:
            full.update(env)
        if path is not None:
            full["PATH"] = str(path)
        return subprocess.run(
            [_BASH, "-c", f"source '{_SCRIPT}'; {func_call}"],
            capture_output=True,
            text=True,
            env=full,
            cwd=str(cwd),
        )

    return _run


def escreve_registro(
    directory,
    record_name: str,
    *,
    ph: float | None = 7.26,
    n_amostras: int = 240,
    sig_name: tuple[str, ...] = ("FHR", "UC"),
    fhr_base: float = 140.0,
    uc_base: float = 20.0,
    fs: int = FS,
) -> str:
    """Escreve um par .hea/.dat válido e devolve o caminho sem extensão."""
    rng = np.random.default_rng(0)
    n_sig = len(sig_name)
    colunas = [rng.normal(fhr_base, 5.0, n_amostras)]
    colunas += [rng.normal(uc_base, 2.0, n_amostras) for _ in range(n_sig - 1)]
    sinal = np.column_stack(colunas).astype(float)

    comments = ["-- Outcome measures"]
    if ph is not None:
        comments.append(f"pH           {ph}")
    comments.append("Apgar1       8")

    wfdb.wrsamp(
        record_name,
        fs=fs,
        units=["bpm", "nd"][:n_sig],
        sig_name=list(sig_name),
        p_signal=sinal,
        fmt=["16"] * n_sig,
        comments=comments,
        write_dir=str(directory),
    )
    return str(directory / record_name)


@pytest.fixture
def escritor():
    """Devolve a função de escrita para testes que montam seus próprios lotes."""
    return escreve_registro


@pytest.fixture
def registro_valido(tmp_path):
    return escreve_registro(tmp_path, "0001", ph=7.26)


@pytest.fixture
def registro_patologico(tmp_path):
    return escreve_registro(tmp_path, "0002", ph=7.01)
