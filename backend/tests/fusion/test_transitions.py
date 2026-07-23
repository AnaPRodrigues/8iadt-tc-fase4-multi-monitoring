"""Testes de `pipelines.fusion.transitions` -- log de auditoria de transição de nível
(FUSION-06)."""

import json
from pathlib import Path

from common.evidence import Evidence
from pipelines.fusion.hysteresis import HysteresisClassifier
from pipelines.fusion.models import FusionEvent, RiskPoint, Transition
from pipelines.fusion.transitions import record_transition, save_transitions


def _ponto(t: float, score: float, contributions: dict[str, float], **overrides) -> RiskPoint:
    defaults = dict(
        t=t,
        score=score,
        level="",
        contributions=contributions,
        missing_modalities=[],
        contributing_events=[],
    )
    return RiskPoint(**{**defaults, **overrides})


def test_record_transition_grava_nivel_anterior_novo_e_sinais_contribuintes():
    ponto = _ponto(t=120.0, score=0.8, contributions={"video": 0.5, "vitals": 0.3})

    transicao = record_transition("amarelo", "vermelho", ponto)

    assert transicao.previous_level == "amarelo"
    assert transicao.new_level == "vermelho"
    assert transicao.t == 120.0
    assert transicao.point.contributions == {"video": 0.5, "vitals": 0.3}


def test_sequencia_de_riskpoints_com_mudanca_de_nivel_gera_log_de_transicao_correto():
    # Percorre uma sequência conhecida de scores via HysteresisClassifier (T7) e
    # registra uma Transition sempre que o nível muda -- confirma a integração real
    # entre o classificador com memória e o log de auditoria.
    classifier = HysteresisClassifier(
        threshold_amarelo=0.3, threshold_vermelho=0.7, hysteresis=0.05
    )
    scores_por_t = [(0.0, 0.1), (60.0, 0.4), (120.0, 0.32), (180.0, 0.8), (240.0, 0.2)]

    transicoes: list[Transition] = []
    nivel_anterior = classifier.level
    for t, score in scores_por_t:
        ponto = _ponto(t=t, score=score, contributions={"video": score})
        novo_nivel = classifier.update(score)
        if novo_nivel != nivel_anterior:
            transicoes.append(record_transition(nivel_anterior, novo_nivel, ponto))
        nivel_anterior = novo_nivel

    # Só 3 dos 5 pontos realmente mudam de nível (t=60 sobe, t=120 fica dentro da
    # banda e não gera transição, t=180 sobe, t=240 desce).
    assert [(tr.t, tr.previous_level, tr.new_level) for tr in transicoes] == [
        (60.0, "verde", "amarelo"),
        (180.0, "amarelo", "vermelho"),
        (240.0, "vermelho", "verde"),
    ]


def test_save_transitions_grava_json_legivel_com_path_reais_serializados(tmp_path: Path):
    evidence = Evidence(
        feature="video_pose",
        run_id="run-1",
        evidence_id="fall-01-fall",
        source_record_id="fall-01",
        artifact_path=Path("output/video_pose/run-1/fall-01-fall.png"),
        sidecar_path=Path("output/video_pose/run-1/fall-01-fall.json"),
    )
    evento = FusionEvent(
        modality="video",
        demo_timestamp_s=10.0,
        severity=1.0,
        summary="queda detectada",
        evidence=evidence,
    )
    ponto = _ponto(
        t=60.0,
        score=0.8,
        contributions={"video": 0.8},
        contributing_events=[evento],
    )
    transicao = record_transition("amarelo", "vermelho", ponto)
    destino = tmp_path / "sub" / "transitions.json"

    save_transitions([transicao], destino)

    assert destino.is_file()
    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert len(dados) == 1
    assert dados[0]["previous_level"] == "amarelo"
    assert dados[0]["new_level"] == "vermelho"
    evento_serializado = dados[0]["point"]["contributing_events"][0]
    caminho_artefato = evento_serializado["evidence"]["artifact_path"]
    assert caminho_artefato == "output/video_pose/run-1/fall-01-fall.png"


def test_save_transitions_lista_vazia_grava_array_json_vazio(tmp_path: Path):
    destino = tmp_path / "transitions.json"

    save_transitions([], destino)

    assert json.loads(destino.read_text(encoding="utf-8")) == []
