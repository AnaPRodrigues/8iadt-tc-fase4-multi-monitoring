"""Orquestra o processamento de ponta a ponta de uma prescrição.

Extrai o texto do PDF (por pdfplumber no modo local ou Amazon Textract no modo
aws), estrutura os campos, aplica as regras clínicas (dose fora da faixa e
variação abrupta em relação à prescrição anterior) e, havendo anomalia, grava a
evidência reproduzível.

O histórico do paciente (a prescrição anterior do mesmo medicamento, usada pela
regra de variação abrupta) é recebido por parâmetro — quem chama busca esse
registro na sua fonte de dados e o injeta aqui. Assim o processamento não depende
de nenhum banco específico.
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from aws.adapters import get_text_extractor
from aws.adapters.cloud import register_cloud_adapters
from aws.clients import resolve_env
from common.evidence import save_evidence
from common.logging import get_logger
from pipelines.prescription.adapters import register_local_adapters
from pipelines.prescription.models import (
    AnomalyResult,
    ParseFailure,
    PrescriptionRecord,
    ProcessResult,
)
from pipelines.prescription.parser import parse_prescription
from pipelines.prescription.rules import evaluate_prescription

log = get_logger("prescription.logic")


def _evidence_id(record: PrescriptionRecord) -> str:
    return f"{record.patient_id}-{record.drug}-{record.timestamp}".replace(":", "-")


def _save_anomaly_evidence(
    pdf_bytes: bytes,
    record: PrescriptionRecord,
    anomalies: list[AnomalyResult],
    source_id: str,
) -> str:
    # Severidade depende do tipo de anomalia e da criticalidade do fármaco.
    # Dose acima da faixa com fármaco de Alta Vigilância (MAV, criticality=3)
    # → CRITICAL (alerta VERMELHO). Criticality ≤2 → HIGH (AMARELO).
    kinds = {a.kind for a in anomalies}
    if "dose_fora_de_faixa" in kinds:
        from pipelines.prescription import catalog

        drug_range = catalog.lookup(record.drug)
        if drug_range and drug_range.criticality >= 3:
            severidade = "CRITICAL"
        else:
            severidade = "HIGH"
    elif "substituicao_critica" in kinds:
        severidade = "HIGH"
    elif "mudanca_abrupta" in kinds:
        severidade = "MEDIUM"
    else:
        severidade = "MEDIUM"

    run_id = datetime.now(UTC).strftime("%Y%m%d")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        tmp_path = Path(f.name)
    try:
        evidence = save_evidence(
            feature="prescription",
            run_id=run_id,
            evidence_id=_evidence_id(record),
            source_record_id=source_id,
            artifact_path=tmp_path,
            metadata={
                "patient_id": record.patient_id,
                "drug": record.drug,
                "dose": record.dose,
                "unit": record.unit,
                "anomalies": [{"kind": a.kind, "reason": a.reason} for a in anomalies],
            },
            severity=severidade,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return evidence.evidence_id


def _ensure_extractor_registrado() -> None:
    """Garante que o extrator de texto do modo ativo está registrado (idempotente)."""
    if resolve_env() == "aws":
        register_cloud_adapters()
    else:
        register_local_adapters()


def process(
    pdf_bytes: bytes,
    source_id: str,
    previous_record: PrescriptionRecord | None = None,
) -> ProcessResult:
    """Processa um PDF de prescrição: extrai, parseia, aplica regras, gera evidência.

    ``source_id`` identifica a origem do documento (ex.: nome do arquivo), só para
    rastrear a evidência. ``previous_record`` é a prescrição anterior do mesmo
    paciente/medicamento, usada pela regra de variação abrupta; ``None`` quando não
    há histórico.
    """
    _ensure_extractor_registrado()

    try:
        extracted = get_text_extractor().extract(pdf_bytes)
    except Exception as exc:
        log.warning("documento ilegível %s: %s", source_id, exc)
        return ProcessResult(
            record=None,
            anomalies=[],
            evidence_id=None,
            parse_failure=ParseFailure(reason="documento ilegível", field="documento"),
        )

    parsed = parse_prescription(extracted)
    if isinstance(parsed, ParseFailure):
        log.warning("falha ao ler a prescrição %s: %s", source_id, parsed.reason)
        return ProcessResult(
            record=None,
            anomalies=[],
            evidence_id=None,
            parse_failure=parsed,
        )

    # Orquestra as 3 regras por ordem de gravidade clínica:
    # 1. dose_fora_de_faixa (superdosagem)
    # 2. substituicao_critica (troca por fármaco de maior risco)
    # 3. mudanca_abrupta (variação percentual no mesmo fármaco)
    all_results = evaluate_prescription(parsed, previous_record)
    anomalies = [r for r in all_results if r.kind != "normal"]

    evidence_id = None
    if anomalies:
        evidence_id = _save_anomaly_evidence(pdf_bytes, parsed, anomalies, source_id)

    return ProcessResult(
        record=parsed,
        anomalies=anomalies,
        evidence_id=evidence_id,
        parse_failure=None,
    )
