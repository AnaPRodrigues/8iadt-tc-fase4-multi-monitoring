"""Configuração declarativa de F2 (YAML → dataclass validada).

Reaplica o *padrão* de validação de ``common/config.py`` (campo desconhecido é
erro, obrigatórios explícitos) sem importar a classe: ``common/config.py`` é, na
prática, específica de ``vitals`` (ver design.md § Tech Decisions e § Risks).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REQUIRED = ("icbhi_dataset_dir",)

DEFAULTS: dict[str, Any] = {
    "icbhi_max_patients": 40,
    "consult_audio_paths": [],
    "critical_terms_path": None,
    "whisper_model_size": "small",
    "no_speech_threshold": 0.6,
    "sentiment_threshold": 0.2,
    "fatigue_threshold": 1.0,
    "seed": 42,
    "output_root": "output",
}


@dataclass(frozen=True)
class Config:
    icbhi_dataset_dir: Path
    icbhi_max_patients: int
    consult_audio_paths: list[Path]
    critical_terms_path: Path | None
    whisper_model_size: str
    no_speech_threshold: float
    sentiment_threshold: float
    fatigue_threshold: float
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
    critical_terms_path = merged["critical_terms_path"]

    return Config(
        icbhi_dataset_dir=Path(merged["icbhi_dataset_dir"]),
        icbhi_max_patients=int(merged["icbhi_max_patients"]),
        consult_audio_paths=[Path(p) for p in merged["consult_audio_paths"]],
        critical_terms_path=Path(critical_terms_path) if critical_terms_path else None,
        whisper_model_size=str(merged["whisper_model_size"]),
        no_speech_threshold=float(merged["no_speech_threshold"]),
        sentiment_threshold=float(merged["sentiment_threshold"]),
        fatigue_threshold=float(merged["fatigue_threshold"]),
        seed=int(merged["seed"]),
        output_root=Path(merged["output_root"]),
    )
