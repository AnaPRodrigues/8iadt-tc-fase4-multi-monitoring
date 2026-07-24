"""Testes do banco local de pacientes (SQLite) e do repositório.

Cada teste usa um banco temporário isolado (via `APP_DB_PATH`), sem tocar o
banco real nem depender de rede/Docker.
"""

import pytest

from app import repositorio


@pytest.fixture(autouse=True)
def _banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))


def test_criar_e_listar_paciente():
    p = repositorio.criar_paciente("Paciente Um", observacoes="internado")

    listados = repositorio.listar_pacientes()

    assert len(listados) == 1
    assert listados[0].id == p.id
    assert listados[0].nome == "Paciente Um"
    assert listados[0].observacoes == "internado"


def test_obter_paciente_inexistente_devolve_none():
    assert repositorio.obter_paciente("nao-existe") is None


def test_remover_paciente_apaga_em_cascata_uploads_analises_alertas():
    p = repositorio.criar_paciente("Alvo")
    u = repositorio.criar_upload(p.id, "documento", "/caminho/x.pdf", "x.pdf")
    repositorio.criar_analise(u.id, "documento", {"resumo": "ok"}, 0.0)
    repositorio.registrar_alerta(p.id, "vermelho", 0.9, "motivo", ["ev-1"])

    assert repositorio.remover_paciente(p.id) is True

    assert repositorio.obter_paciente(p.id) is None
    assert repositorio.listar_uploads(p.id) == []
    assert repositorio.listar_analises_do_paciente(p.id) == []
    assert repositorio.listar_alertas_do_paciente(p.id) == []


def test_remover_paciente_inexistente_devolve_false():
    assert repositorio.remover_paciente("nao-existe") is False


def test_upload_nasce_com_situacao_recebido_e_atualiza():
    p = repositorio.criar_paciente("P")
    u = repositorio.criar_upload(p.id, "video", "/caminho/seq", "seq")

    assert u.situacao == "recebido"

    repositorio.atualizar_situacao_upload(u.id, "concluido")

    assert repositorio.obter_upload(u.id).situacao == "concluido"


def test_analise_guarda_resultado_json_e_pontuacao():
    p = repositorio.criar_paciente("P")
    u = repositorio.criar_upload(p.id, "audio", "/caminho/a.wav", "a.wav")

    a = repositorio.criar_analise(
        u.id, "audio", {"resumo": "sibilo", "detalhes": {"ciclo": 1}}, 0.46
    )

    recuperada = repositorio.obter_analise_de_upload(u.id)
    assert recuperada.resultado == {"resumo": "sibilo", "detalhes": {"ciclo": 1}}
    assert recuperada.pontuacao == 0.46
    assert a.id == recuperada.id


def test_listar_analises_do_paciente_junta_por_upload():
    p = repositorio.criar_paciente("P")
    u1 = repositorio.criar_upload(p.id, "documento", "/x.pdf", "x.pdf")
    u2 = repositorio.criar_upload(p.id, "video", "/seq", "seq")
    repositorio.criar_analise(u1.id, "documento", {"resumo": "a"}, 1.0)
    repositorio.criar_analise(u2.id, "video", {"resumo": "b"}, 0.0)

    analises = repositorio.listar_analises_do_paciente(p.id)

    assert {a.modalidade for a in analises} == {"documento", "video"}


def test_alerta_guarda_referencias_e_motivo_clinico():
    p = repositorio.criar_paciente("P")

    al = repositorio.registrar_alerta(
        p.id, "vermelho", 0.82, "sibilo + aumento de dose", ["ev-a", "ev-b"]
    )

    do_paciente = repositorio.listar_alertas_do_paciente(p.id)
    assert len(do_paciente) == 1
    assert do_paciente[0].nivel == "vermelho"
    assert do_paciente[0].motivo == "sibilo + aumento de dose"
    assert do_paciente[0].referencias == ["ev-a", "ev-b"]
    assert al.id == do_paciente[0].id


def test_listar_todos_os_alertas_atravessa_pacientes():
    p1 = repositorio.criar_paciente("P1")
    p2 = repositorio.criar_paciente("P2")
    repositorio.registrar_alerta(p1.id, "amarelo", 0.4, "m1", [])
    repositorio.registrar_alerta(p2.id, "vermelho", 0.8, "m2", [])

    assert len(repositorio.listar_todos_os_alertas()) == 2
