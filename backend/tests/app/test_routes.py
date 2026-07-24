"""Testes de integração da API (FastAPI `TestClient`): pacientes, envios,
análises, linha do tempo, alertas e evidências.

Banco e uploads em diretórios temporários; o despacho de análise é substituído
por um dublê, então nenhum teste depende dos conjuntos de dados ou dos pipelines
pesados.
"""

import pytest
from fastapi.testclient import TestClient

from app import routes, servico
from app.analise import ResultadoAnalise
from common.evidence import save_evidence

client = TestClient(routes.app)


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("APP_UPLOADS_DIR", str(tmp_path / "uploads"))
    output_root = tmp_path / "output"
    monkeypatch.setattr(servico, "_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(routes, "_OUTPUT_ROOT", output_root)
    return output_root


# --------------------------------------------------------------------------- #
# Pacientes
# --------------------------------------------------------------------------- #
def test_criar_listar_obter_e_remover_paciente():
    criado = client.post("/patients", json={"nome": "Paciente Um", "observacoes": "UTI"})
    assert criado.status_code == 201
    pid = criado.json()["id"]
    assert criado.json()["nivel_atual"] == "verde"

    assert len(client.get("/patients").json()) == 1
    assert client.get(f"/patients/{pid}").json()["nome"] == "Paciente Um"

    assert client.delete(f"/patients/{pid}").status_code == 204
    assert client.get(f"/patients/{pid}").status_code == 404


def test_criar_paciente_sem_nome_recusa():
    assert client.post("/patients", json={"nome": "   "}).status_code == 422


def test_obter_paciente_inexistente_404():
    assert client.get("/patients/nao-existe").status_code == 404


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def test_enviar_arquivo_e_listar_uploads():
    pid = client.post("/patients", json={"nome": "P"}).json()["id"]

    envio = client.post(
        f"/patients/{pid}/uploads",
        params={"modalidade": "documento"},
        files={"arquivo": ("receita.pdf", b"conteudo", "application/pdf")},
    )
    assert envio.status_code == 201
    assert envio.json()["situacao"] == "recebido"
    assert envio.json()["modalidade"] == "documento"

    uploads = client.get(f"/patients/{pid}/uploads").json()
    assert len(uploads) == 1
    assert uploads[0]["nome_original"] == "receita.pdf"


def test_enviar_arquivo_modalidade_invalida_recusa():
    pid = client.post("/patients", json={"nome": "P"}).json()["id"]

    resp = client.post(
        f"/patients/{pid}/uploads",
        params={"modalidade": "raio-x"},
        files={"arquivo": ("x.bin", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_enviar_arquivo_para_paciente_inexistente_404():
    resp = client.post(
        "/patients/nao-existe/uploads",
        params={"modalidade": "documento"},
        files={"arquivo": ("x.pdf", b"x", "application/pdf")},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Análise
# --------------------------------------------------------------------------- #
def _upload(pid, modalidade="documento"):
    return client.post(
        f"/patients/{pid}/uploads",
        params={"modalidade": modalidade},
        files={"arquivo": ("f.pdf", b"x", "application/pdf")},
    ).json()["id"]


def test_disparar_analise_reaproveita_o_despacho_e_grava_resultado(_ambiente, monkeypatch):
    pid = client.post("/patients", json={"nome": "P"}).json()["id"]
    uid = _upload(pid)

    def _dublê(upload, caminho):
        return ResultadoAnalise(
            resumo="Losartana 100 mg — aumento de 100% em relação à dose anterior",
            pontuacao=1.0,
            evidencia_id=None,
            detalhes={},
        )

    monkeypatch.setattr(servico, "_despachar", _dublê)

    resp = client.post(f"/uploads/{uid}/analyze")
    assert resp.status_code == 200
    assert "aumento de 100%" in resp.json()["resumo"]

    # e o resultado fica consultável
    consulta = client.get(f"/uploads/{uid}/analysis")
    assert consulta.status_code == 200
    assert consulta.json()["upload_id"] == uid


def test_consultar_analise_antes_de_analisar_404():
    pid = client.post("/patients", json={"nome": "P"}).json()["id"]
    uid = _upload(pid)

    assert client.get(f"/uploads/{uid}/analysis").status_code == 404


def test_analisar_envio_inexistente_404():
    assert client.post("/uploads/nao-existe/analyze").status_code == 404


# --------------------------------------------------------------------------- #
# Linha do tempo e alertas
# --------------------------------------------------------------------------- #
def _semear_evento(_ambiente, pid, modalidade, feature, evidence_id, instante_s, monkeypatch):
    """Cria um upload + análise com achado e evidência real, via o despacho dublê."""
    artefato = _ambiente / "_stage" / f"{evidence_id}.txt"
    artefato.parent.mkdir(parents=True, exist_ok=True)
    artefato.write_text("evid")
    save_evidence(
        feature=feature,
        run_id="r",
        evidence_id=evidence_id,
        source_record_id="rec",
        artifact_path=artefato,
        metadata={},
        root=_ambiente,
    )
    uid = _upload(pid, modalidade)

    def _dublê(upload, caminho):
        return ResultadoAnalise(
            resumo=f"achado em {modalidade}",
            pontuacao=1.0,
            evidencia_id=evidence_id,
            detalhes={"instante_s": instante_s},
        )

    monkeypatch.setattr(servico, "_despachar", _dublê)
    client.post(f"/uploads/{uid}/analyze")


def test_timeline_e_alertas_do_paciente(_ambiente, monkeypatch):
    pid = client.post("/patients", json={"nome": "P"}).json()["id"]
    for mod, feat, ev in [
        ("video", "video_pose", "ev-v"),
        ("audio", "audio", "ev-a"),
        ("sinais_vitais", "vitals", "ev-s"),
        ("documento", "prescription", "ev-d"),
    ]:
        _semear_evento(_ambiente, pid, mod, feat, ev, 0.0, monkeypatch)

    timeline = client.get(f"/patients/{pid}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()) >= 1
    assert timeline.json()[-1]["level"] == "vermelho"

    # o alerta foi registrado automaticamente ao cruzar o limiar
    alertas = client.get(f"/patients/{pid}/alerts").json()
    assert len(alertas) == 1
    assert alertas[0]["nivel"] == "vermelho"

    # e o paciente agora reporta nível atual vermelho
    assert client.get(f"/patients/{pid}").json()["nivel_atual"] == "vermelho"

    # lista geral de alertas inclui este
    assert len(client.get("/alerts").json()) == 1


def test_timeline_paciente_inexistente_404():
    assert client.get("/patients/nao-existe/timeline").status_code == 404


# --------------------------------------------------------------------------- #
# Evidência
# --------------------------------------------------------------------------- #
def test_obter_evidencia_serve_o_artefato(_ambiente):
    artefato = _ambiente / "_stage" / "ev-1.txt"
    artefato.parent.mkdir(parents=True, exist_ok=True)
    artefato.write_text("conteudo da evidência")
    save_evidence(
        feature="video_pose",
        run_id="r",
        evidence_id="ev-1",
        source_record_id="rec",
        artifact_path=artefato,
        metadata={},
        root=_ambiente,
    )

    resp = client.get("/evidence/ev-1")
    assert resp.status_code == 200
    assert resp.text == "conteudo da evidência"
    assert resp.headers["x-evidence-feature"] == "video_pose"


def test_obter_evidencia_inexistente_404():
    assert client.get("/evidence/nao-existe").status_code == 404
