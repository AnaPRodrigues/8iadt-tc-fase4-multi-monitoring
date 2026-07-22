"""Testes de integração de `handler.py` contra LocalStack real (T11).

Requer `make localstack-up`. Pula com mensagem clara se o LocalStack não
responder em :4566. Nomeado `test_video_handler.py` (não `test_handler.py`)
para não colidir com `backend/tests/integration/test_prescription_...`.
"""

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aws.clients import get_client
from aws.provision import ensure_bucket
from pipelines.video.adapters import register_local_adapters
from pipelines.video.handler import lambda_handler

_ENDOSCAPES_TRAIN = (
    Path(__file__).resolve().parents[3] / "data" / "endoscapes" / "endoscapes" / "train"
)
_FRAME = _ENDOSCAPES_TRAIN / "8_14775.jpg"


def _localstack_disponivel() -> bool:
    try:
        with socket.create_connection(("localhost", 4566), timeout=2):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _localstack_disponivel(),
        reason="LocalStack não está de pé em :4566 — rode `make localstack-up`",
    ),
]


@pytest.fixture(autouse=True)
def _env_local(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")


@pytest.fixture(autouse=True)
def _adapter_local(finetuned_weights):
    register_local_adapters(finetuned_weights)


@pytest.fixture
def bucket():
    import uuid

    nome = f"mm-test-video-bucket-{uuid.uuid4().hex[:8]}"
    ensure_bucket(nome)
    return nome


def _s3_event(bucket: str, key: str, etag: str) -> dict:
    return {"Records": [{"s3": {"bucket": {"name": bucket}, "object": {"key": key, "eTag": etag}}}]}


def _evidence_dir() -> Path:
    run_id = datetime.now(UTC).strftime("%Y%m%d")
    return Path("output") / "video_cloud" / run_id


def _find_sidecar(bucket: str, key: str) -> Path | None:
    """Localiza o sidecar pelo `source_record_id`, sem presumir a codificação do nome."""
    dest_dir = _evidence_dir()
    if not dest_dir.is_dir():
        return None
    source_record_id = f"{bucket}/{key}"
    for sidecar in dest_dir.glob("*.json"):
        if json.loads(sidecar.read_text(encoding="utf-8"))["source_record_id"] == source_record_id:
            return sidecar
    return None


def test_handler_processa_keyframe_real_e_gera_evidencia(bucket):
    client = get_client("s3")
    key = "keyframes/8_14775.jpg"
    client.put_object(Bucket=bucket, Key=key, Body=_FRAME.read_bytes())
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    response = lambda_handler(_s3_event(bucket, key, etag), context=None)

    assert response["statusCode"] == 200
    sidecar_path = _find_sidecar(bucket, key)
    assert sidecar_path is not None
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["source_record_id"] == f"{bucket}/{key}"
    assert "labels" in sidecar["metadata"]
    assert (sidecar_path.parent / sidecar["artifact"]).is_file()


def test_handler_falha_do_analyzer_nao_derruba_o_handler(bucket, monkeypatch):
    import pipelines.video.handler as handler_module

    def _quebrado():
        class _Broken:
            def analyze(self, image_bytes):
                raise RuntimeError("analyzer indisponível")

        return _Broken()

    monkeypatch.setattr(handler_module, "get_image_analyzer", _quebrado)

    client = get_client("s3")
    key = "keyframes/quebrado.jpg"
    client.put_object(Bucket=bucket, Key=key, Body=_FRAME.read_bytes())
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    response = lambda_handler(_s3_event(bucket, key, etag), context=None)

    assert response["statusCode"] == 200
    assert _find_sidecar(bucket, key) is None


def test_handler_reenvio_do_mesmo_objeto_nao_duplica_evidencia(bucket):
    client = get_client("s3")
    key = "keyframes/reenvio.jpg"
    client.put_object(Bucket=bucket, Key=key, Body=_FRAME.read_bytes())
    etag = client.head_object(Bucket=bucket, Key=key)["ETag"]

    lambda_handler(_s3_event(bucket, key, etag), context=None)
    lambda_handler(_s3_event(bucket, key, etag), context=None)

    dest_dir = _evidence_dir()
    source_record_id = f"{bucket}/{key}"
    matching_sidecars = [
        s
        for s in dest_dir.glob("*.json")
        if json.loads(s.read_text(encoding="utf-8"))["source_record_id"] == source_record_id
    ]

    # reprocessar o mesmo objeto sobrescreve o sidecar em vez de duplicá-lo
    assert len(matching_sidecars) == 1
