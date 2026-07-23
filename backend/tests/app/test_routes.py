"""Testes de integração (FastAPI `TestClient`) das rotas de timeline/análise do
paciente-demo -- FUSION-10 (parte)."""

import yaml
from fastapi.testclient import TestClient

from app import routes
from common.evidence import save_evidence


def _grava_evidencia(output_root, feature, run_id, evidence_id, metadata):
    tmp_dir = output_root / "_staging"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    artifact = tmp_dir / f"{evidence_id}.txt"
    artifact.write_text("conteudo de evidência de teste")
    return save_evidence(
        feature=feature,
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id="rec-1",
        artifact_path=artifact,
        metadata=metadata,
        root=output_root,
    )


def _escreve_config(configs_dir, patient_demo_id, events, **overrides):
    config = {"patient_demo_id": patient_demo_id, "events": events, **overrides}
    (configs_dir / f"{patient_demo_id}.yaml").write_text(yaml.safe_dump(config))


def _fixture_ambiente(tmp_path, monkeypatch):
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    output_root = tmp_path / "output"
    monkeypatch.setattr(routes, "_CONFIGS_DIR", configs_dir)
    monkeypatch.setattr(routes, "_OUTPUT_ROOT", output_root)
    return configs_dir, output_root


client = TestClient(routes.app)


# ---------- GET /patients/{id}/timeline ----------


def test_get_timeline_devolve_pontos_classificados_rodando_o_motor_de_ponta_a_ponta(
    tmp_path, monkeypatch
):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    _escreve_config(
        configs_dir,
        "demo-teste",
        [
            {
                "modality": "video",
                "feature": "video",
                "run_id": "run-1",
                "evidence_id": "fall-01",
                "demo_timestamp_s": 0.0,
                "severity": 1.0,
            }
        ],
    )

    response = client.get("/patients/demo-teste/timeline")

    assert response.status_code == 200
    pontos = response.json()
    assert len(pontos) >= 1
    assert pontos[0]["contributing_events"][0]["evidence_id"] == "fall-01"
    assert pontos[0]["contributing_events"][0]["summary"] == "queda=detectada"
    # o nível vem classificado pelo HysteresisClassifier, não fica "" (bruto do risk_engine)
    assert pontos[0]["level"] in ("verde", "amarelo", "vermelho")


def test_get_timeline_paciente_demo_inexistente_devolve_404(tmp_path, monkeypatch):
    _fixture_ambiente(tmp_path, monkeypatch)

    response = client.get("/patients/nao-existe/timeline")

    assert response.status_code == 404
    assert "nao-existe" in response.json()["detail"]


# ---------- GET /analyze ----------


def test_analyze_devolve_nivel_score_e_modalidades_ausentes_do_ponto_mais_recente(
    tmp_path, monkeypatch
):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    _escreve_config(
        configs_dir,
        "demo-teste",
        [
            {
                "modality": "video",
                "feature": "video",
                "run_id": "run-1",
                "evidence_id": "fall-01",
                "demo_timestamp_s": 0.0,
                "severity": 1.0,
            }
        ],
        window_size_s=60.0,
    )

    timeline = client.get("/patients/demo-teste/timeline").json()
    response = client.get("/analyze", params={"patient_demo_id": "demo-teste"})

    assert response.status_code == 200
    ponto = response.json()
    # /analyze devolve exatamente o último ponto da mesma timeline (mesmo motor)
    assert ponto["t"] == timeline[-1]["t"]
    assert ponto["level"] == timeline[-1]["level"]
    assert set(ponto["missing_modalities"]) == {"audio", "vitals", "prescription"}


def test_analyze_paciente_demo_inexistente_devolve_404(tmp_path, monkeypatch):
    _fixture_ambiente(tmp_path, monkeypatch)

    response = client.get("/analyze", params={"patient_demo_id": "nao-existe"})

    assert response.status_code == 404
    assert "nao-existe" in response.json()["detail"]


# ---------- GET /alerts ----------


def _config_que_dispara_vermelho(configs_dir, patient_demo_id="demo-alerta"):
    # peso 1.0 só em vídeo -- severidade 1.0 no evento cruza vermelho+histerese (0.75)
    # já no primeiro ponto da timeline (score_at(0, ...) = 1.0 * 1.0 * decay(0) = 1.0).
    _escreve_config(
        configs_dir,
        patient_demo_id,
        [
            {
                "modality": "video",
                "feature": "video",
                "run_id": "run-1",
                "evidence_id": "fall-01",
                "demo_timestamp_s": 0.0,
                "severity": 1.0,
            }
        ],
        weights={"video": 1.0},
        window_size_s=60.0,
    )


def test_get_alerts_lista_transicao_que_cruza_o_nivel_de_disparo_confirmada(
    tmp_path, monkeypatch
):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    _config_que_dispara_vermelho(configs_dir)
    monkeypatch.setattr(routes, "_is_confirmed", lambda dedup_key: True)

    response = client.get("/alerts", params={"patient_demo_id": "demo-alerta"})

    assert response.status_code == 200
    alertas = response.json()
    assert len(alertas) == 1
    assert alertas[0]["previous_level"] == "verde"
    assert alertas[0]["new_level"] == "vermelho"
    assert alertas[0]["confirmed"] is True
    assert alertas[0]["contributions"][0][0] == "video"


def test_get_alerts_alerta_nao_confirmado_quando_dynamodb_nao_tem_o_dedup_key(
    tmp_path, monkeypatch
):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    _config_que_dispara_vermelho(configs_dir)
    monkeypatch.setattr(routes, "_is_confirmed", lambda dedup_key: False)

    response = client.get("/alerts", params={"patient_demo_id": "demo-alerta"})

    alertas = response.json()
    assert len(alertas) == 1
    assert alertas[0]["confirmed"] is False


def test_get_alerts_sem_dynamodb_table_configurada_reporta_nao_confirmado_sem_quebrar(
    tmp_path, monkeypatch
):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    _config_que_dispara_vermelho(configs_dir)
    monkeypatch.delenv("DYNAMODB_TABLE", raising=False)

    response = client.get("/alerts", params={"patient_demo_id": "demo-alerta"})

    assert response.status_code == 200
    assert response.json()[0]["confirmed"] is False


def test_get_alerts_sem_transicao_de_disparo_devolve_lista_vazia(tmp_path, monkeypatch):
    configs_dir, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})
    # pesos default (0.25 cada) -- score máximo 0.25, nunca cruza nenhum limiar
    _escreve_config(
        configs_dir,
        "demo-sem-alerta",
        [
            {
                "modality": "video",
                "feature": "video",
                "run_id": "run-1",
                "evidence_id": "fall-01",
                "demo_timestamp_s": 0.0,
                "severity": 1.0,
            }
        ],
    )

    response = client.get("/alerts", params={"patient_demo_id": "demo-sem-alerta"})

    assert response.status_code == 200
    assert response.json() == []


def test_get_alerts_paciente_demo_inexistente_devolve_404(tmp_path, monkeypatch):
    _fixture_ambiente(tmp_path, monkeypatch)

    response = client.get("/alerts", params={"patient_demo_id": "nao-existe"})

    assert response.status_code == 404
    assert "nao-existe" in response.json()["detail"]


# ---------- GET /evidence/{id} ----------


def test_get_evidence_serve_o_artefato_real_com_content_type_e_metadados_no_header(
    tmp_path, monkeypatch
):
    _, output_root = _fixture_ambiente(tmp_path, monkeypatch)
    _grava_evidencia(output_root, "video", "run-1", "fall-01", {"queda": "detectada"})

    response = client.get("/evidence/fall-01")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "conteudo de evidência de teste"
    assert response.headers["x-evidence-feature"] == "video"
    assert response.headers["x-evidence-run-id"] == "run-1"


def test_get_evidence_id_inexistente_devolve_404(tmp_path, monkeypatch):
    _fixture_ambiente(tmp_path, monkeypatch)

    response = client.get("/evidence/nao-existe")

    assert response.status_code == 404
    assert "nao-existe" in response.json()["detail"]
