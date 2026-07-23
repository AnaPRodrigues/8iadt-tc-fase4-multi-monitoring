"""Handler Lambda fino do complemento de análise de vídeo na nuvem.

Lê o evento S3, roda o `ImageAnalyzer` já registrado para o `ENV` ativo e anexa
os labels como evidência complementar. Falha/timeout do analyzer é logada e
não propaga -- mesmo padrão usado no pipeline de prescrições (não trava o processamento do lote).
"""

import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aws.adapters import get_image_analyzer
from aws.clients import get_client
from common.evidence import save_evidence
from common.logging import get_logger

log = get_logger("video.handler")

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")


def _evidence_id(bucket: str, key: str) -> str:
    """Nome determinístico a partir de bucket+key -- reenviar o mesmo objeto
    sobrescreve a evidência em vez de duplicá-la (idempotência por nome)."""
    return _UNSAFE_CHARS.sub("-", f"{bucket}-{key}")


def _handle_record(record: dict) -> None:
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]
    client = get_client("s3")

    try:
        obj = client.get_object(Bucket=bucket, Key=key)
        image_bytes = obj["Body"].read()
        analysis = get_image_analyzer().analyze(image_bytes)
    except Exception:
        log.exception("falha ao analisar %s/%s -- processamento segue sem evidência", bucket, key)
        return

    evidence_id = _evidence_id(bucket, key)
    run_id = datetime.now(UTC).strftime("%Y%m%d")
    suffix = Path(key).suffix or ".jpg"

    with tempfile.TemporaryDirectory() as tmp_dir:
        artifact_path = Path(tmp_dir) / f"{evidence_id}{suffix}"
        artifact_path.write_bytes(image_bytes)
        save_evidence(
            feature="video_cloud",
            run_id=run_id,
            evidence_id=evidence_id,
            source_record_id=f"{bucket}/{key}",
            artifact_path=artifact_path,
            metadata={
                "labels": [
                    {"name": label.name, "confidence": label.confidence}
                    for label in analysis.labels
                ]
            },
        )

    log.info("keyframe %s/%s analisado: %d label(s)", bucket, key, len(analysis.labels))


def lambda_handler(event: dict[str, Any], context: Any) -> dict:
    """Handler Lambda: processa cada registro do evento S3 (`Records`)."""
    for record in event.get("Records", []):
        _handle_record(record)
    return {"statusCode": 200}
