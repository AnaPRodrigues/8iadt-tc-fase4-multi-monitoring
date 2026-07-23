"""Testes do score heurístico de fadiga vocal."""

from pipelines.audio.fatigue_score import is_fatigued, score
from pipelines.audio.models import AcousticFeatures


def _features(jitter, shimmer, hnr, pause_rate, speaking_rate) -> AcousticFeatures:
    return AcousticFeatures(
        jitter_local=jitter,
        shimmer_local=shimmer,
        hnr_db=hnr,
        pause_rate=pause_rate,
        speaking_rate_wps=speaking_rate,
    )


_BASELINE = [
    _features(0.005, 0.020, 20.0, 0.10, 3.0),
    _features(0.008, 0.030, 18.0, 0.15, 2.8),
    _features(0.006, 0.025, 19.0, 0.12, 2.9),
]


def test_audio_fala_lenta_e_pausada_produz_score_maior_que_audio_normal():
    """Fala mais lenta/pausada produz score de fadiga maior que fala normal."""
    normal = _features(0.006, 0.025, 19.0, 0.12, 2.9)  # próximo da média do baseline
    lento_e_pausado = _features(0.020, 0.060, 10.0, 0.30, 1.5)  # jitter/shimmer/pausa maiores,
    # HNR/velocidade de fala menores -- exatamente o padrão de fadiga

    score_normal = score(normal, _BASELINE)
    score_fatigado = score(lento_e_pausado, _BASELINE)

    assert score_fatigado > score_normal


def test_is_fatigued_respeita_o_threshold_configuravel():
    valor = 1.5

    assert is_fatigued(valor, threshold=1.0) is True
    assert is_fatigued(valor, threshold=2.0) is False


def test_baseline_de_um_unico_elemento_nao_levanta_excecao():
    unico = _features(0.010, 0.040, 15.0, 0.20, 2.0)
    diferente = _features(0.030, 0.090, 8.0, 0.40, 1.0)

    resultado = score(diferente, [unico])

    assert resultado == 0.0  # desvio-padrão zero em toda feature: nenhum componente contribui
