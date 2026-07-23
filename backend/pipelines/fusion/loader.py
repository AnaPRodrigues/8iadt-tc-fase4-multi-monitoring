"""Resolve cada `CuratedEventRef` da config do paciente-demo em um `FusionEvent` real,
lendo o sidecar JSON já gravado por F1-F4 (mesmo contrato de `common/evidence.py`).

Não usa `save_evidence` -- F5 não cria evidência nova nesta etapa, só lê o que já
existe em disco (FUSION-01).
"""

import json
from pathlib import Path
from typing import Any

from common.evidence import Evidence, evidence_dir
from common.logging import get_logger
from pipelines.fusion.config import PatientDemoConfig
from pipelines.fusion.models import CuratedEventRef, FusionEvent

log = get_logger("fusion.loader")


def _summary(metadata: dict[str, Any]) -> str:
    """Resumo textual compacto a partir do metadata real.

    O metadata não tem um schema comum entre as 4 features de origem (cada uma grava
    seus próprios campos) -- o resumo é a representação key=value do metadata inteiro,
    não uma extração de campo específico por modalidade.
    """
    return ", ".join(f"{k}={v}" for k, v in metadata.items())


def _resolve(ref: CuratedEventRef, output_root: Path) -> FusionEvent:
    sidecar_path = evidence_dir(ref.feature, ref.run_id, output_root) / f"{ref.evidence_id}.json"
    if not sidecar_path.is_file():
        raise FileNotFoundError(f"evidência inexistente: {sidecar_path}")

    raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    evidence = Evidence(
        feature=raw["feature"],
        run_id=raw["run_id"],
        evidence_id=raw["evidence_id"],
        source_record_id=raw["source_record_id"],
        artifact_path=sidecar_path.parent / raw["artifact"],
        sidecar_path=sidecar_path,
    )
    return FusionEvent(
        modality=ref.modality,
        demo_timestamp_s=ref.demo_timestamp_s,
        severity=ref.severity,
        summary=_summary(raw["metadata"]),
        evidence=evidence,
    )


def load_events(
    config: PatientDemoConfig, output_root: Path
) -> tuple[list[FusionEvent], list[str]]:
    """Resolve cada evento curado da config em `FusionEvent` real.

    Uma referência que não resolve (arquivo ausente) é reportada na segunda lista
    (tolerância a falha, mesmo padrão de `vitals/loader.load_dataset`) -- não derruba
    a carga inteira.
    """
    events: list[FusionEvent] = []
    falhas: list[str] = []

    for ref in config.events:
        try:
            events.append(_resolve(ref, Path(output_root)))
        except FileNotFoundError as exc:
            log.warning("falha ao resolver evento curado: %s", exc)
            falhas.append(str(exc))

    return events, falhas
