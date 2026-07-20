"""Carga de configuração declarativa (YAML) do pipeline.

Um campo desconhecido é erro, não aviso: num arquivo de config, `taus` no lugar de
`tau` falharia silenciosamente com o default, e o relatório reportaria métricas de um
limiar que o usuário acha que mudou.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REQUIRED = ("dataset_dir",)

DEFAULTS: dict[str, Any] = {
    "window_size_s": 60.0,
    "window_stride_s": 30.0,
    "zscore_threshold": 3.0,
    "iforest_contamination": 0.1,
    "tau": 0.15,  # AD-027
    "seed": 42,
    "output_root": "output",
}

_NUMERIC = (
    "window_size_s",
    "window_stride_s",
    "zscore_threshold",
    "iforest_contamination",
    "tau",
)


@dataclass(frozen=True)
class Config:
    dataset_dir: Path
    window_size_s: float
    window_stride_s: float
    zscore_threshold: float
    iforest_contamination: float
    tau: float
    seed: int
    output_root: Path


def load_config(path: Path) -> Config:
    """Lê e valida a config, aplicando os defaults documentados em ``DEFAULTS``."""
    if not Path(path).is_file():
        raise FileNotFoundError(f"config inexistente: {path}")

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config precisa ser um mapa de chave/valor")

    known = set(_REQUIRED) | set(DEFAULTS)
    for key in raw:
        if key not in known:
            raise ValueError(f"campo desconhecido na config: {key}")

    for key in _REQUIRED:
        if key not in raw:
            raise ValueError(f"campo obrigatório ausente na config: {key}")

    merged = {**DEFAULTS, **raw}

    for key in _NUMERIC:
        if isinstance(merged[key], bool) or not isinstance(merged[key], int | float):
            raise ValueError(f"campo {key} precisa ser numérico, recebido: {merged[key]!r}")

    if isinstance(merged["seed"], bool) or not isinstance(merged["seed"], int):
        raise ValueError(f"campo seed precisa ser inteiro, recebido: {merged['seed']!r}")

    return Config(
        dataset_dir=Path(merged["dataset_dir"]),
        window_size_s=float(merged["window_size_s"]),
        window_stride_s=float(merged["window_stride_s"]),
        zscore_threshold=float(merged["zscore_threshold"]),
        iforest_contamination=float(merged["iforest_contamination"]),
        tau=float(merged["tau"]),
        seed=int(merged["seed"]),
        output_root=Path(merged["output_root"]),
    )
