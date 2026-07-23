"""Testes do sentimento local pt-BR."""

import inspect

from pipelines.audio import sentiment as sentiment_module
from pipelines.audio.sentiment import classify


def test_texto_sem_palavra_do_lexico_e_neutro_com_score_zero():
    resultado = classify("Isso é apenas um teste sem palavra do dicionário.", threshold=0.2)

    assert resultado.score == 0.0
    assert resultado.label == "neutro"


def test_texto_majoritariamente_positivo_e_classificado_como_positivo():
    resultado = classify("Estou bem, estou bem, mas com dor.", threshold=0.2)

    assert resultado.label == "positivo"


def test_texto_majoritariamente_negativo_e_classificado_como_negativo():
    resultado = classify("Estou mal, estou mal, mas bem.", threshold=0.2)

    assert resultado.label == "negativo"


def test_threshold_configuravel_muda_a_classificacao_do_mesmo_texto():
    texto = "Estou bem, estou bem, mas com dor."

    resultado_limiar_baixo = classify(texto, threshold=0.2)
    resultado_limiar_alto = classify(texto, threshold=0.5)

    assert resultado_limiar_baixo.score == resultado_limiar_alto.score
    assert resultado_limiar_baixo.label == "positivo"
    assert resultado_limiar_alto.label == "neutro"
    assert resultado_limiar_baixo.label != resultado_limiar_alto.label


def test_modulo_nao_importa_cliente_de_nuvem():
    """Sentimento precisa ser 100% local, garantido por construção."""
    fonte = inspect.getsource(sentiment_module)

    assert "boto3" not in fonte
    assert "requests" not in fonte
    assert "urllib" not in fonte
