"""Contrato único de evidência do projeto.

Toda anomalia detectada — em qualquer modalidade — produz um artefato visual e um
sidecar JSON de metadados no mesmo formato. É o que permite ao dashboard de fusão e alertas fazer
drill-down de qualquer feature sem tratar cada uma como caso especial.

``AnomalyEvent`` é um tipo específico de ``vitals``, mas ``core`` precisa ser
genérico (vídeo grava frame, áudio espectrograma, prescrição PDF). Os metadados são portanto um
mapa livre, e ``source_record_id`` virou parâmetro explícito por ser proveniência —
uma exigência transversal a todas as features, não só ao monitoramento de sinais vitais.
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DEFAULT_ROOT = "output"

# --------------------------------------------------------------------------- #
# Níveis de severidade e status — semântica compartilhada entre pipelines
# --------------------------------------------------------------------------- #

# Severidade do evento detectado. A fusão usa estes níveis para ponderar
# o risk score: CRITICAL pesa mais que LOW.
SEVERITY_LEVELS = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")

# Status da análise: positive = anomalia encontrada, negative = analisado e
# nada encontrado, unavailable = pipeline indisponível (ex.: arquivo corrompido),
# inconclusive = analisado mas sem confiança suficiente para decidir.
ANALYSIS_STATUS = ("positive", "negative", "unavailable", "inconclusive")


def severity_weight(severity: str) -> float:
    """Peso base para cada nível de severidade na fusão.

    CRITICAL → 1.0, HIGH → 0.7, MEDIUM → 0.45, LOW → 0.2, INFO → 0.05.
    Valores fora do vocabulário devolvem 0.1 (desconhecido, conservador).
    """
    _weights = {"CRITICAL": 1.0, "HIGH": 0.7, "MEDIUM": 0.45, "LOW": 0.2, "INFO": 0.05}
    return _weights.get(severity.upper(), 0.1)


@dataclass(frozen=True)
class Evidence:
    feature: str
    run_id: str
    evidence_id: str
    source_record_id: str
    artifact_path: Path
    sidecar_path: Path
    # -- novos campos opcionais (aditivos, não quebram compatibilidade) --
    modality: str = ""                # "video" | "audio" | "vitals" | "prescription"
    event_type: str = ""              # "fall" | "trunk_tilt" | "crackle" | "dose_fora_de_faixa" | ...
    severity: str = "MEDIUM"          # INFO | LOW | MEDIUM | HIGH | CRITICAL
    confidence: float = 0.0           # 0–1
    timestamp: str = ""               # ISO-8601
    patient_id: str = ""              # id do paciente no banco local
    status: str = "positive"          # positive | negative | unavailable | inconclusive
    metadata: dict[str, Any] = field(default_factory=dict)


def evidence_dir(feature: str, run_id: str, root: str | Path = _DEFAULT_ROOT) -> Path:
    """Diretório canónico de evidências: ``<root>/<feature>/<run_id>``."""
    return Path(root) / feature / run_id


def save_evidence(
    *,
    feature: str,
    run_id: str,
    evidence_id: str,
    source_record_id: str,
    artifact_path: Path,
    metadata: dict[str, Any] | None = None,
    root: str | Path = _DEFAULT_ROOT,
    # -- novos campos opcionais --
    modality: str = "",
    event_type: str = "",
    severity: str = "MEDIUM",
    confidence: float = 0.0,
    timestamp: str = "",
    patient_id: str = "",
    status: str = "positive",
) -> Evidence:
    """Copia o artefato para o diretório de evidências e grava o sidecar de metadados.

    ``source_record_id`` identifica o registro de origem — na timeline composta
    é o registro real de onde o trecho veio.

    Os campos *modality*, *event_type*, *severity*, *confidence*, *timestamp*,
    *patient_id* e *status* são opcionais (default vazio/zero) para não quebrar
    as pipelines existentes — podem ser adicionados incrementalmente.
    """
    if not artifact_path.is_file():
        raise FileNotFoundError(f"artefacto inexistente: {artifact_path}")

    dest_dir = evidence_dir(feature, run_id, root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_artifact = dest_dir / artifact_path.name
    if dest_artifact.resolve() != artifact_path.resolve():
        shutil.copy2(artifact_path, dest_artifact)

    ts = timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sidecar_path = dest_dir / f"{evidence_id}.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "evidence_id": evidence_id,
                "feature": feature,
                "run_id": run_id,
                "source_record_id": source_record_id,
                "artifact": dest_artifact.name,
                "metadata": metadata or {},
                # novos campos
                "modality": modality,
                "event_type": event_type,
                "severity": severity,
                "confidence": confidence,
                "timestamp": ts,
                "patient_id": patient_id,
                "status": status,
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
        modality=modality,
        event_type=event_type,
        severity=severity,
        confidence=confidence,
        timestamp=ts,
        patient_id=patient_id,
        status=status,
        metadata=metadata or {},
    )
