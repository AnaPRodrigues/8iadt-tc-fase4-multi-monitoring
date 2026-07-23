"""Testes de `pipelines.fusion.hysteresis.HysteresisClassifier` -- classificação com
histerese e memória de estado entre janelas (FUSION-05, FUSION-13)."""

from pipelines.fusion.hysteresis import HysteresisClassifier

# Mesmos defaults documentados em `fusion/config.py`.
_THRESHOLD_AMARELO = 0.3
_THRESHOLD_VERMELHO = 0.7
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

    assert c.update(0.1) == "verde"


def test_classifica_amarelo_quando_score_cruza_o_limiar_amarelo_mais_a_histerese():
    c = _classifier()

    assert c.update(0.36) == "amarelo"  # > 0.3 + 0.05


def test_classifica_vermelho_quando_score_cruza_o_limiar_vermelho_mais_a_histerese():
    c = _classifier(initial_level="amarelo")

    assert c.update(0.76) == "vermelho"  # > 0.7 + 0.05


def test_salto_direto_de_verde_para_vermelho_sem_passar_por_amarelo():
    c = _classifier()

    assert c.update(0.9) == "vermelho"


def test_salto_direto_de_vermelho_para_verde_sem_passar_por_amarelo():
    c = _classifier(initial_level="vermelho")

    assert c.update(0.1) == "verde"


def test_histerese_evita_oscilacao_com_score_variando_dentro_da_banda_do_limiar():
    # Nível já em amarelo; score oscila entre 0.28 e 0.32 -- dentro da banda
    # [0.3 - 0.05, 0.3 + 0.05] = [0.25, 0.35] -- nunca deveria sair de amarelo.
    c = _classifier(initial_level="amarelo")

    niveis = [c.update(s) for s in [0.28, 0.32, 0.29, 0.31, 0.30, 0.33]]

    assert niveis == ["amarelo"] * 6


def test_mantem_o_ultimo_nivel_quando_score_nao_cruza_a_banda_fusion_13():
    # Sobe para vermelho, depois o score cai um pouco por decaimento mas não o
    # suficiente para cruzar a banda de saída (limiar_vermelho - histerese = 0.65) --
    # o nível precisa continuar "vermelho", nunca resetar por ausência de sinal novo.
    c = _classifier()
    assert c.update(0.9) == "vermelho"

    assert c.update(0.7) == "vermelho"
    assert c.update(0.66) == "vermelho"


def test_sequencia_conhecida_bate_com_calculo_manual():
    # Sequência de scores conhecida percorrendo os 3 níveis, com um trecho de
    # oscilação perto do limiar amarelo no meio -- cálculo manual esperado:
    # 0.1 -> verde (abaixo de tudo)
    # 0.4 -> amarelo (cruza 0.35)
    # 0.32 -> amarelo (dentro da banda, sem cruzar 0.25 nem 0.75)
    # 0.28 -> amarelo (idem, ainda dentro da banda)
    # 0.8 -> vermelho (cruza 0.75)
    # 0.5 -> amarelo (cai abaixo de 0.65, mas não abaixo de 0.25)
    # 0.2 -> verde (cai abaixo de 0.25)
    c = _classifier()
    scores = [0.1, 0.4, 0.32, 0.28, 0.8, 0.5, 0.2]
    esperado = ["verde", "amarelo", "amarelo", "amarelo", "vermelho", "amarelo", "verde"]

    niveis = [c.update(s) for s in scores]

    assert niveis == esperado


def test_property_level_reflete_a_ultima_chamada_a_update_sem_reavaliar():
    c = _classifier()
    c.update(0.9)

    assert c.level == "vermelho"
