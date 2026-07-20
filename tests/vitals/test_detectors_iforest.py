"""Testes do detector IsolationForest multivariado (VITALS-04, VITALS-09)."""

import pytest

from vitals.detectors import Detector, IsolationForestDetector
from vitals.features import FeatureVector


def _fv(media: float, decel: float = 0.0, *, valid: bool = True) -> FeatureVector:
    if not valid:
        nan = float("nan")
        return FeatureVector(nan, nan, nan, nan, nan, nan, nan, valid=False)
    return FeatureVector(
        mean=media, std=2.0, min=media - 5, max=media + 5,
        baseline=media, short_term_variability=1.5,
        deceleration_count=decel, valid=True,
    )


def _serie_normal(n: int = 30) -> list[FeatureVector]:
    return [_fv(140.0 + (i % 3)) for i in range(n)]


def test_implementa_o_protocolo_detector():
    assert isinstance(IsolationForestDetector(contamination=0.1, seed=42), Detector)


def test_mesma_seed_produz_scores_identicos():
    serie = _serie_normal()

    a = IsolationForestDetector(contamination=0.1, seed=42).score(serie)
    b = IsolationForestDetector(contamination=0.1, seed=42).score(serie)

    assert a == b


def test_outlier_multivariado_recebe_score_mais_alto_que_a_massa():
    serie = [*_serie_normal(30), _fv(210.0, decel=8.0)]

    scores = IsolationForestDetector(contamination=0.1, seed=42).score(serie)
    normais = [s for s in scores[:-1] if s is not None]

    assert scores[-1] > max(normais)


def test_outlier_multivariado_e_marcado():
    serie = [*_serie_normal(30), _fv(210.0, decel=8.0)]

    flags = IsolationForestDetector(contamination=0.1, seed=42).flag(serie)

    assert flags[-1] is True


def test_contamination_e_configuravel_e_muda_quantas_janelas_sao_marcadas():
    """Dois valores distintos precisam produzir resultados distintos, senão está hardcoded."""
    serie = [*_serie_normal(40), _fv(210.0, decel=8.0), _fv(205.0, decel=7.0)]

    poucas = IsolationForestDetector(contamination=0.05, seed=42).flag(serie)
    muitas = IsolationForestDetector(contamination=0.4, seed=42).flag(serie)

    assert sum(1 for f in muitas if f) > sum(1 for f in poucas if f)


def test_contamination_fora_do_intervalo_valido_e_rejeitado():
    with pytest.raises(ValueError, match="contamination"):
        IsolationForestDetector(contamination=0.9, seed=42)


def test_seeds_diferentes_produzem_scores_diferentes():
    """Contraparte do determinismo: a seed precisa REALMENTE alimentar o modelo.

    Sem asserir `a != b`, fixar `random_state=0` e ignorar a seed configurada
    passaria despercebido — foi exatamente o que aconteceu na iteração anterior.
    """
    serie = [*_serie_normal(40), _fv(210.0, decel=8.0)]

    a = IsolationForestDetector(contamination=0.1, seed=1).score(serie)
    b = IsolationForestDetector(contamination=0.1, seed=999).score(serie)

    assert a != b


def test_a_seed_configurada_e_a_que_alimenta_o_modelo():
    """Vizinho do caso acima: uma seed distinta de 0 não pode coincidir com seed=0."""
    serie = [*_serie_normal(40), _fv(210.0, decel=8.0)]

    zero = IsolationForestDetector(contamination=0.1, seed=0).score(serie)
    outra = IsolationForestDetector(contamination=0.1, seed=12345).score(serie)

    assert zero != outra


def test_janela_insuficiente_recebe_none_e_nao_entra_no_treino():
    serie = [*_serie_normal(30), _fv(0.0, valid=False)]
    d = IsolationForestDetector(contamination=0.1, seed=42)

    scores = d.score(serie)
    flags = d.flag(serie)

    assert scores[-1] is None
    assert flags[-1] is None
    # o treino usou apenas as 30 janelas válidas
    assert d.n_treino == 30


def test_conjunto_pequeno_demais_reporta_insuficiente_sem_excecao():
    serie = _serie_normal(3)
    d = IsolationForestDetector(contamination=0.1, seed=42)

    scores = d.score(serie)

    assert all(s is None for s in scores)
    assert d.insufficient_data is True


def test_serie_so_com_janelas_invalidas_nao_quebra():
    serie = [_fv(0.0, valid=False) for _ in range(5)]
    d = IsolationForestDetector(contamination=0.1, seed=42)

    assert all(s is None for s in d.score(serie))
    assert d.insufficient_data is True


def test_serie_vazia_nao_quebra():
    d = IsolationForestDetector(contamination=0.1, seed=42)

    assert d.score([]) == []
