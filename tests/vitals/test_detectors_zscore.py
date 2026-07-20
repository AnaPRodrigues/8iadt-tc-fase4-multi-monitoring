"""Testes do detector rolling z-score (VITALS-03)."""

import math

import pytest

from vitals.detectors import Detector, RollingZScoreDetector
from vitals.features import FeatureVector

BASELINE = [138.0, 140.0, 142.0, 139.0, 141.0]  # média 140, desvio sqrt(2)


def _fv(media: float, *, valid: bool = True) -> FeatureVector:
    if not valid:
        nan = float("nan")
        return FeatureVector(nan, nan, nan, nan, nan, nan, nan, valid=False)
    return FeatureVector(
        mean=media, std=1.0, min=media, max=media,
        baseline=media, short_term_variability=1.0,
        deceleration_count=0.0, valid=True,
    )


def _serie(medias: list[float]) -> list[FeatureVector]:
    return [_fv(m) for m in medias]


def test_implementa_o_protocolo_detector():
    assert isinstance(RollingZScoreDetector(threshold=3.0, baseline_size=5), Detector)


def test_serie_sem_anomalia_nao_marca_nada():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    flags = d.flag(_serie([*BASELINE, 140.0, 139.0, 141.0]))

    assert not any(f for f in flags if f)


def test_outlier_isolado_e_marcado():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    flags = d.flag(_serie([*BASELINE, 200.0]))

    assert flags[-1] is True


def test_valor_acima_do_limiar_e_marcado():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    # desvio de 5 bpm / sqrt(2) ≈ 3.54 > 3.0
    scores = d.score(_serie([*BASELINE, 145.0]))

    assert scores[-1] == pytest.approx(5 / math.sqrt(2))
    assert d.flag(_serie([*BASELINE, 145.0]))[-1] is True


def test_valor_abaixo_do_limiar_nao_e_marcado():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    # desvio de 4 bpm / sqrt(2) ≈ 2.83 < 3.0
    assert d.flag(_serie([*BASELINE, 144.0]))[-1] is False


def test_limiar_e_configuravel_e_muda_o_resultado():
    serie = _serie([*BASELINE, 144.0])

    assert RollingZScoreDetector(threshold=3.0, baseline_size=5).flag(serie)[-1] is False
    assert RollingZScoreDetector(threshold=2.0, baseline_size=5).flag(serie)[-1] is True


def test_score_exatamente_no_limiar_nao_e_marcado():
    """Comparação estrita `> threshold`, coerente com a fronteira de AD-027."""
    d = RollingZScoreDetector(threshold=math.sqrt(2), baseline_size=5)

    # desvio de 2 bpm / sqrt(2) = sqrt(2), exatamente o limiar
    serie = _serie([*BASELINE, 142.0])

    assert d.score(serie)[-1] == pytest.approx(math.sqrt(2))
    assert d.flag(serie)[-1] is False


def test_baseline_constante_nao_divide_por_zero():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    scores = d.score(_serie([140.0] * 5 + [160.0]))

    assert math.isinf(scores[-1])


def test_baseline_constante_com_valor_identico_tem_score_zero():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    scores = d.score(_serie([140.0] * 5 + [140.0]))

    assert scores[-1] == 0.0


def test_janela_insuficiente_recebe_none_nunca_zero():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)
    serie = [*_serie(BASELINE), _fv(0.0, valid=False)]

    scores = d.score(serie)
    flags = d.flag(serie)

    assert scores[-1] is None
    assert flags[-1] is None


def test_sem_baseline_suficiente_o_score_e_none():
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)

    scores = d.score(_serie([140.0, 141.0]))

    assert all(s is None for s in scores)


def test_janela_invalida_nao_entra_no_baseline():
    """Uma janela descartada não pode contaminar a estatística de referência."""
    d = RollingZScoreDetector(threshold=3.0, baseline_size=5)
    serie = [*_serie(BASELINE[:2]), _fv(0.0, valid=False), *_serie(BASELINE[2:]), _fv(145.0)]

    scores = d.score(serie)

    assert scores[-1] == pytest.approx(5 / math.sqrt(2))

