"""Testes de core.metrics — derivados dos ACs da spec de vitals-anomaly (VITALS-06, VITALS-10)."""

import json

import pytest

from core.metrics import MetricsReport, binary_metrics, save_report


def test_caso_balanceado_calcula_precision_recall_f1():
    # TP=2 (idx 0,4), FP=1 (idx 3), FN=1 (idx 1), TN=1 (idx 2)
    y_true = [True, True, False, False, True]
    y_pred = [True, False, False, True, True]

    r = binary_metrics(y_true, y_pred, detector="zscore")

    assert r.precision == pytest.approx(2 / 3)
    assert r.recall == pytest.approx(2 / 3)
    assert r.f1 == pytest.approx(2 / 3)
    assert r.support == 3
    assert r.detector == "zscore"


def test_predicao_perfeita_zera_erros():
    y_true = [True, False, True]
    y_pred = [True, False, True]

    r = binary_metrics(y_true, y_pred, detector="iforest")

    assert r.precision == 1.0
    assert r.recall == 1.0
    assert r.f1 == 1.0
    assert r.support == 2


def test_sem_positivos_reais_deixa_recall_indefinido():
    """VITALS-10: nenhum registro patológico ⇒ recall indefinido, nunca 0.0 silencioso."""
    y_true = [False, False, False]
    y_pred = [True, False, False]

    r = binary_metrics(y_true, y_pred, detector="zscore")

    assert r.recall is None
    assert r.support == 0
    # Houve predição positiva, mas nenhuma correta: precision é definida e vale 0.0
    assert r.precision == 0.0
    assert r.f1 is None


def test_sem_predicoes_positivas_deixa_precision_indefinida():
    y_true = [True, False, True]
    y_pred = [False, False, False]

    r = binary_metrics(y_true, y_pred, detector="zscore")

    assert r.precision is None
    assert r.recall == 0.0
    assert r.f1 is None
    assert r.support == 2


def test_listas_vazias_deixam_metricas_indefinidas():
    r = binary_metrics([], [], detector="zscore")

    assert r.precision is None
    assert r.recall is None
    assert r.f1 is None
    assert r.support == 0


def test_comprimentos_divergentes_sao_rejeitados():
    with pytest.raises(ValueError, match="mesmo comprimento"):
        binary_metrics([True, False], [True], detector="zscore")


def test_save_report_grava_json_legivel(tmp_path):
    r = MetricsReport(detector="zscore", precision=0.5, recall=None, f1=None, support=4)
    dest = tmp_path / "sub" / "metrics.json"

    save_report(r, dest)

    payload = json.loads(dest.read_text(encoding="utf-8"))
    assert payload["detector"] == "zscore"
    assert payload["precision"] == 0.5
    assert payload["recall"] is None
    assert payload["support"] == 4
