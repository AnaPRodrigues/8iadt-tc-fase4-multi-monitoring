"""Configuração declarativa do paciente-demo (YAML -> dataclass validada).

Mesmo *padrão* de validação de `pipelines/audio/config.py` (campo desconhecido é
erro, obrigatórios explícitos), não uma classe compartilhada -- ver design.md
("Reuses" de `fusion/config.py`). Não é "1 registro por modalidade": é uma lista
curada de eventos (AD-045a), cada um resolvido depois por `loader.py`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipelines.fusion.models import CuratedEventRef

_VALID_MODALITIES = {"video", "audio", "vitals", "prescription"}

_REQUIRED = ("patient_demo_id", "events")

DEFAULTS: dict[str, Any] = {
    "weights": {"video": 0.25, "audio": 0.25, "vitals": 0.25, "prescription": 0.25},
    "decay_half_life_s": 600.0,
    "threshold_amarelo": 0.3,
    "threshold_vermelho": 0.7,
    "hysteresis": 0.05,
    "window_size_s": 60.0,
    "alert_level": "vermelho",
}


@dataclass(frozen=True)
class PatientDemoConfig:
    patient_demo_id: str
    events: list[CuratedEventRef]
    weights: dict[str, float]
    decay_half_life_s: float
    threshold_amarelo: float
    threshold_vermelho: float
    hysteresis: float
    window_size_s: float
    alert_level: str


def _parse_event(raw: dict[str, Any]) -> CuratedEventRef:
    modality = raw.get("modality")
    if modality not in _VALID_MODALITIES:
        raise ValueError(
            f"modality inválida em evento curado: {modality!r} "
            f"(esperado um de {sorted(_VALID_MODALITIES)})"
        )
    return CuratedEventRef(
        modality=modality,
        feature=str(raw["feature"]),
        run_id=str(raw["run_id"]),
        evidence_id=str(raw["evidence_id"]),
        demo_timestamp_s=float(raw["demo_timestamp_s"]),
        severity=float(raw.get("severity", 1.0)),
    )


def load_patient_demo_config(path: Path) -> PatientDemoConfig:
    """Lê e valida a config do paciente-demo, aplicando os defaults documentados em `DEFAULTS`."""
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

    events_raw = raw["events"]
    if not events_raw:
        raise ValueError("events precisa ter ao menos 1 item")

    merged = {**DEFAULTS, **raw}

    return PatientDemoConfig(
        patient_demo_id=str(merged["patient_demo_id"]),
        events=[_parse_event(e) for e in events_raw],
        weights=dict(merged["weights"]),
        decay_half_life_s=float(merged["decay_half_life_s"]),
        threshold_amarelo=float(merged["threshold_amarelo"]),
        threshold_vermelho=float(merged["threshold_vermelho"]),
        hysteresis=float(merged["hysteresis"]),
        window_size_s=float(merged["window_size_s"]),
        alert_level=str(merged["alert_level"]),
    )
