"""Testes de core.evidence — contrato único de evidência (AD-026, VITALS-06, VITALS-07)."""

import json

import pytest

from core.evidence import evidence_dir, save_evidence


def _artefato(tmp_path):
    art = tmp_path / "grafico.png"
    art.write_bytes(b"fake-png")
    return art


def test_evidence_dir_segue_convencao_output_feature_run():
    d = evidence_dir("vitals", "run-42", root="output")

    assert d.as_posix() == "output/vitals/run-42"


def test_save_evidence_grava_sidecar_com_metadados_e_proveniencia(tmp_path):
    art = _artefato(tmp_path)

    ev = save_evidence(
        feature="vitals",
        run_id="run-1",
        evidence_id="ev-001",
        source_record_id="1464",
        artifact_path=art,
        metadata={"detector": "zscore", "score": 3.7, "ph": 7.01},
        root=tmp_path / "out",
    )

    sidecar = json.loads(ev.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["source_record_id"] == "1464"
    assert sidecar["evidence_id"] == "ev-001"
    assert sidecar["metadata"]["detector"] == "zscore"
    assert sidecar["metadata"]["score"] == 3.7
    assert sidecar["metadata"]["ph"] == 7.01


def test_save_evidence_cria_diretorio_inexistente(tmp_path):
    art = _artefato(tmp_path)
    root = tmp_path / "nao" / "existe"

    ev = save_evidence(
        feature="vitals",
        run_id="run-1",
        evidence_id="ev-001",
        source_record_id="1464",
        artifact_path=art,
        metadata={},
        root=root,
    )

    assert ev.sidecar_path.exists()
    assert ev.sidecar_path.parent == root / "vitals" / "run-1"


def test_artefato_ausente_e_rejeitado(tmp_path):
    with pytest.raises(FileNotFoundError, match="artefato"):
        save_evidence(
            feature="vitals",
            run_id="run-1",
            evidence_id="ev-001",
            source_record_id="1464",
            artifact_path=tmp_path / "nao-existe.png",
            metadata={},
            root=tmp_path / "out",
        )


def test_evidencia_referencia_o_artefato_gravado(tmp_path):
    art = _artefato(tmp_path)

    ev = save_evidence(
        feature="vitals",
        run_id="run-1",
        evidence_id="ev-001",
        source_record_id="1464",
        artifact_path=art,
        metadata={},
        root=tmp_path / "out",
    )

    sidecar = json.loads(ev.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["artifact"] == art.name
    assert (ev.sidecar_path.parent / sidecar["artifact"]).read_bytes() == b"fake-png"
