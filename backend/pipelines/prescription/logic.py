"""Orquestra o processamento de ponta a ponta de uma prescrição (PRESC-02/06).

Chamado pelo handler Lambda fino (`handler.py`). Nenhuma dependência de AWS além
das já resolvidas por `aws.adapters`/`history` — testável sem mock de rede além
do LocalStack real (integration).
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from aws.adapters import get_text_extractor
from common.evidence import save_evidence
from common.logging import get_logger
from pipelines.prescription import history
from pipelines.prescription.adapters import register_local_adapters
from pipelines.prescription.models import (
    AnomalyResult,
    ParseFailure,
    PrescriptionRecord,
    ProcessResult,
)
from pipelines.prescription.parser import parse_prescription
from pipelines.prescription.rules import check_abrupt_change, check_dose_range

log = get_logger("prescription.logic")


def _evidence_id(record: PrescriptionRecord) -> str:
    return f"{record.patient_id}-{record.drug}-{record.timestamp}".replace(":", "-")


def _save_anomaly_evidence(
    pdf_bytes: bytes,
    record: PrescriptionRecord,
    anomalies: list[AnomalyResult],
    bucket: str,
    key: str,
) -> str:
    run_id = datetime.now(UTC).strftime("%Y%m%d")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp_path = Path(f.name)
    try:
        evidence = save_evidence(
            feature="prescription",
            run_id=run_id,
            evidence_id=_evidence_id(record),
            source_record_id=f"{bucket}/{key}",
            artifact_path=tmp_path,
            metadata={
                "patient_id": record.patient_id,
                "drug": record.drug,
                "dose": record.dose,
                "unit": record.unit,
                "anomalies": [{"kind": a.kind, "reason": a.reason} for a in anomalies],
            },
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return evidence.evidence_id


def process(pdf_bytes: bytes, bucket: str, key: str, etag: str) -> ProcessResult:
    """Processa um PDF de prescrição: extrai, parseia, aplica regras, persiste."""
    # Idempotente — só garante que "local" está no registro, mesmo se um teste
    # anterior tiver isolado/limpo o dict (aws.adapters._TEXT_EXTRACTORS).
    register_local_adapters()

    dedup = history.dedup_key(bucket, key, etag)

    extracted = get_text_extractor().extract(pdf_bytes)
    parsed = parse_prescription(extracted)
    if isinstance(parsed, ParseFailure):
        log.warning("falha de parsing em %s/%s: %s", bucket, key, parsed.reason)
        return ProcessResult(
            record=None,
            anomalies=[],
            evidence_id=None,
            deduplicated=False,
            parse_failure=parsed,
        )

    previous = history.get_latest(parsed.patient_id, parsed.drug)
    saved = history.save_record(parsed, dedup)
    if not saved:
        log.info("evento %s/%s já processado (dedup)", bucket, key)
        return ProcessResult(
            record=parsed,
            anomalies=[],
            evidence_id=None,
            deduplicated=True,
            parse_failure=None,
        )

    anomalies = [
        result
        for result in (check_dose_range(parsed), check_abrupt_change(parsed, previous))
        if result.kind != "normal"
    ]

    evidence_id = None
    if anomalies:
        evidence_id = _save_anomaly_evidence(pdf_bytes, parsed, anomalies, bucket, key)

    return ProcessResult(
        record=parsed,
        anomalies=anomalies,
        evidence_id=evidence_id,
        deduplicated=False,
        parse_failure=None,
    )
