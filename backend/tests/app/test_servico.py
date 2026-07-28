"""Testes da camada de serviço: linha do tempo de risco a partir do banco e
registro automático de alertas ao cruzar o limiar.

Usa evidência real (gravada em um `output/` temporário), mas não roda os
pipelines de detecção — as análises são inseridas direto no banco, e o disparo
de análise é testado com o despacho substituído por um dublê.
"""

import pytest

from app import repositorio, servico
from app.analise import ResultadoAnalise
from common.evidence import save_evidence


@pytest.fixture(autouse=True)
def _ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    output_root = tmp_path / "output"
    monkeypatch.setattr(servico, "_OUTPUT_ROOT", output_root)
    return output_root


def _grava_evidencia(output_root, feature, evidence_id):
    artefato = output_root / "_stage" / f"{evidence_id}.txt"
    artefato.parent.mkdir(parents=True, exist_ok=True)
    artefato.write_text("evidência de teste")
    save_evidence(
        feature=feature,
        run_id="r1",
        evidence_id=evidence_id,
        source_record_id="rec",
        artifact_path=artefato,
        metadata={},
        root=output_root,
        severity="CRITICAL",
    )


def _analise_com_evidencia(paciente_id, modalidade, feature, evidence_id, instante_s, output_root):
    u = repositorio.criar_upload(paciente_id, modalidade, "/x", "x")
    _grava_evidencia(output_root, feature, evidence_id)
    resultado = {
        "resumo": f"achado em {modalidade}",
        "pontuacao": 1.0,
        "evidencia_id": evidence_id,
        "detalhes": {"instante_s": instante_s},
    }
    repositorio.criar_analise(u.id, modalidade, resultado, 1.0)


def test_linha_do_tempo_vazia_quando_paciente_nao_tem_achado(_ambiente):
    p = repositorio.criar_paciente("P")

    assert servico.linha_do_tempo(p.id) == []
    assert servico.nivel_atual(p.id) == "verde"


def test_linha_do_tempo_produz_pontos_classificados(_ambiente):
    p = repositorio.criar_paciente("P")
    _analise_com_evidencia(p.id, "video", "video_pose", "ev-video", 0.0, _ambiente)

    pontos = servico.linha_do_tempo(p.id)

    assert len(pontos) >= 1
    assert pontos[0].contributing_events[0].evidence.evidence_id == "ev-video"
    assert pontos[0].level in ("verde", "amarelo", "vermelho")


def test_analise_sem_anomalia_nao_entra_na_linha_do_tempo(_ambiente):
    p = repositorio.criar_paciente("P")
    u = repositorio.criar_upload(p.id, "video", "/x", "x")
    repositorio.criar_analise(u.id, "video", {"resumo": "sem queda", "evidencia_id": None}, 0.0)

    assert servico.linha_do_tempo(p.id) == []


def test_alerta_registrado_quando_quatro_modalidades_cruzam_o_limiar(_ambiente):
    p = repositorio.criar_paciente("P")
    # 4 modalidades no mesmo instante, severidade 1.0 -> score 4*0.25 = 1.0 > 0.75 (vermelho)
    _analise_com_evidencia(p.id, "video", "video_pose", "ev-v", 0.0, _ambiente)
    _analise_com_evidencia(p.id, "audio", "audio", "ev-a", 0.0, _ambiente)
    _analise_com_evidencia(p.id, "sinais_vitais", "vitals", "ev-s", 0.0, _ambiente)
    _analise_com_evidencia(p.id, "documento", "prescription", "ev-d", 0.0, _ambiente)

    servico._reavaliar_alertas(p.id)

    alertas = repositorio.listar_alertas_do_paciente(p.id)
    assert len(alertas) == 1
    assert alertas[0].nivel == "vermelho"
    assert set(alertas[0].referencias) == {"ev-v", "ev-a", "ev-s", "ev-d"}
    # motivo em linguagem clínica junta os resumos das modalidades
    assert "achado em" in alertas[0].motivo


def test_reavaliar_alertas_nao_duplica_o_mesmo_conjunto(_ambiente):
    p = repositorio.criar_paciente("P")
    for mod, feat, ev in [
        ("video", "video_pose", "ev-v"),
        ("audio", "audio", "ev-a"),
        ("sinais_vitais", "vitals", "ev-s"),
        ("documento", "prescription", "ev-d"),
    ]:
        _analise_com_evidencia(p.id, mod, feat, ev, 0.0, _ambiente)

    servico._reavaliar_alertas(p.id)
    servico._reavaliar_alertas(p.id)  # segunda passada não deve duplicar

    assert len(repositorio.listar_alertas_do_paciente(p.id)) == 1


def test_analisar_upload_grava_resultado_atualiza_situacao_e_dispara_alerta(_ambiente, monkeypatch):
    p = repositorio.criar_paciente("P")
    u = repositorio.criar_upload(p.id, "documento", "/x.pdf", "x.pdf")
    _grava_evidencia(_ambiente, "prescription", "ev-presc")

    def _dublê(upload, caminho):
        return ResultadoAnalise(
            resumo="Losartana 100 mg — aumento de 100% em relação à dose anterior",
            pontuacao=1.0,
            evidencia_id="ev-presc",
            detalhes={"medicamento": "losartana"},
        )

    monkeypatch.setattr(servico, "_despachar", _dublê)

    registro = servico.analisar_upload(u.id)

    assert registro.resultado["resumo"].startswith("Losartana")
    assert repositorio.obter_upload(u.id).situacao == "concluido"


def test_analisar_upload_marca_erro_quando_arquivo_incompativel(_ambiente, monkeypatch):
    from app import analise

    p = repositorio.criar_paciente("P")
    u = repositorio.criar_upload(p.id, "video", "/nao/existe", "seq")

    def _erro(upload, caminho):
        raise analise.ErroDeAnalise("formato inesperado")

    monkeypatch.setattr(servico, "_despachar", _erro)

    servico.analisar_upload(u.id)

    assert repositorio.obter_upload(u.id).situacao == "erro"
