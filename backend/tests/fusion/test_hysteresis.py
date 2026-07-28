"""Testes de `pipelines.fusion.hysteresis.HysteresisClassifier` -- classificação com
histerese e memória de estado entre janelas."""

from pipelines.fusion.hysteresis import HysteresisClassifier

# Mesmos defaults documentados em `fusion/config.py`.
_THRESHOLD_AMARELO = 0.15
_THRESHOLD_VERMELHO = 0.35
_HYSTERESIS = 0.05


def _classifier(initial_level: str = "verde") -> HysteresisClassifier:
    return HysteresisClassifier(
        threshold_amarelo=_THRESHOLD_AMARELO,
        threshold_vermelho=_THRESHOLD_VERMELHO,
        hysteresis=_HYSTERESIS,
        initial_level=initial_level,
    )


def test_classifica_verde_quando_score_abaixo_da_banda_do_limiar_amarelo():
    c = _classifier()

    assert c.update(0.08) == "verde"


def test_classifica_amarelo_quando_score_cruza_o_limiar_amarelo_mais_a_histerese():
    c = _classifier()

    assert c.update(0.21) == "amarelo"  # > 0.15 + 0.05


def test_classifica_vermelho_quando_score_cruza_o_limiar_vermelho_mais_a_histerese():
    c = _classifier(initial_level="amarelo")

    assert c.update(0.41) == "vermelho"  # > 0.35 + 0.05


def test_salto_direto_de_verde_para_vermelho_sem_passar_por_amarelo():
    c = _classifier()

    assert c.update(0.9) == "vermelho"


def test_verde_para_vermelho_respeita_a_fronteira_exata_da_banda_do_limiar_vermelho():
    # 0.9 (teste acima) passa tão longe de 0.40 que não discrimina a fronteira real
    # de threshold_vermelho+histerese -- um score logo abaixo dela (0.39, que já
    # cruzou a banda do amarelo em 0.20) precisa parar em "amarelo", não pular
    # direto pra "vermelho".
    c = _classifier()

    assert c.update(0.39) == "amarelo"  # > 0.15 + 0.05, mas não > 0.35 + 0.05


def test_salto_direto_de_vermelho_para_verde_sem_passar_por_amarelo():
    c = _classifier(initial_level="vermelho")

    assert c.update(0.08) == "verde"  # < 0.15 - 0.05 = 0.10


def test_histerese_evita_oscilacao_com_score_variando_dentro_da_banda_do_limiar():
    # Nível já em amarelo; score oscila entre 0.13 e 0.17 -- dentro da banda
    # [0.15 - 0.05, 0.15 + 0.05] = [0.10, 0.20] -- nunca deveria sair de amarelo.
    c = _classifier(initial_level="amarelo")

    niveis = [c.update(s) for s in [0.13, 0.17, 0.14, 0.16, 0.15, 0.18]]

    assert niveis == ["amarelo"] * 6


def test_mantem_o_ultimo_nivel_quando_score_nao_cruza_a_banda_fusion_13():
    # Sobe para vermelho, depois o score cai um pouco por decaimento mas não o
    # suficiente para cruzar a banda de saída (limiar_vermelho - histerese = 0.30) --
    # o nível precisa continuar "vermelho", nunca resetar por ausência de sinal novo.
    c = _classifier()
    assert c.update(0.9) == "vermelho"

    assert c.update(0.7) == "vermelho"
    assert c.update(0.31) == "vermelho"


def test_sequencia_conhecida_bate_com_calculo_manual():
    # Sequência de scores conhecida percorrendo os 3 níveis, com um trecho de
    # oscilação perto do limiar amarelo no meio -- cálculo manual esperado:
    # 0.05 -> verde (abaixo de 0.20)
    # 0.25 -> amarelo (cruza 0.20)
    # 0.18 -> amarelo (dentro da banda [0.10, 0.20])
    # 0.14 -> amarelo (idem, ainda dentro da banda)
    # 0.8 -> vermelho (cruza 0.40)
    # 0.35 -> vermelho (acima de 0.30, não sai do vermelho)
    # 0.25 -> amarelo (cai abaixo de 0.30, mas não abaixo de 0.10)
    # 0.08 -> verde (cai abaixo de 0.10)
    c = _classifier()
    scores = [0.05, 0.25, 0.18, 0.14, 0.8, 0.35, 0.25, 0.08]
    esperado = ["verde", "amarelo", "amarelo", "amarelo", "vermelho", "vermelho", "amarelo", "verde"]

    niveis = [c.update(s) for s in scores]

    assert niveis == esperado


def test_property_level_reflete_a_ultima_chamada_a_update_sem_reavaliar():
    c = _classifier()
    c.update(0.9)

    assert c.level == "vermelho"
