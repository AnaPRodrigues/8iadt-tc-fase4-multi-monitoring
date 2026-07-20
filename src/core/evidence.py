"""Contrato único de evidência do projeto (AD-026).

Toda anomalia detectada — em qualquer modalidade — produz um artefato visual e um
sidecar JSON de metadados no mesmo formato. É o que permite ao dashboard de F5 fazer
drill-down de qualquer feature sem tratar cada uma como caso especial.

SPEC_DEVIATION: o design assinava ``save_evidence(event: AnomalyEvent, ...)``, mas
``AnomalyEvent`` é um tipo de ``vitals`` e o mesmo design exige que ``core`` seja
genérico (F1 grava frame, F2 espectrograma, F4 PDF). Os metadados são portanto um
mapa livre, e ``source_record_id`` virou parâmetro explícito por ser proveniência —
uma exigência transversal a todas as features, não só a F3 (VITALS-07).
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_ROOT = "output"


@dataclass(frozen=True)
class Evidence:
    feature: str
    run_id: str
    evidence_id: str
    source_record_id: str
    artifact_path: Path
    sidecar_path: Path


def evidence_dir(feature: str, run_id: str, root: str | Path = _DEFAULT_ROOT) -> Path:
    """Diretório canônico de evidências: ``<root>/<feature>/<run_id>``."""
    return Path(root) / feature / run_id


def save_evidence(
    *,
    feature: str,
    run_id: str,
    evidence_id: str,
    source_record_id: str,
    artifact_path: Path,
    metadata: dict[str, Any],
    root: str | Path = _DEFAULT_ROOT,
) -> Evidence:
    """Copia o artefato para o diretório de evidências e grava o sidecar de metadados.

    ``source_record_id`` identifica o registro de origem — na timeline composta de F3
    é o registro real de onde o trecho veio (VITALS-07).
    """
    if not artifact_path.is_file():
        raise FileNotFoundError(f"artefato inexistente: {artifact_path}")

    dest_dir = evidence_dir(feature, run_id, root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_artifact = dest_dir / artifact_path.name
    if dest_artifact.resolve() != artifact_path.resolve():
        shutil.copy2(artifact_path, dest_artifact)

    sidecar_path = dest_dir / f"{evidence_id}.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "evidence_id": evidence_id,
                "feature": feature,
                "run_id": run_id,
                "source_record_id": source_record_id,
                "artifact": dest_artifact.name,
                "metadata": metadata,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return Evidence(
        feature=feature,
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id=source_record_id,
        artifact_path=dest_artifact,
        sidecar_path=sidecar_path,
    )
