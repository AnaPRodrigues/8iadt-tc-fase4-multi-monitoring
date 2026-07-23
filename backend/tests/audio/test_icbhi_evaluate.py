"""Testes da avaliação por classe do classificador ICBHI."""

import json

from pipelines.audio.icbhi_evaluate import evaluate, save_evaluation

CLASSES = ("normal", "crackle", "wheeze", "both")


def test_classe_ausente_do_teste_produz_metricas_none_nunca_zero():
    y_true = ["normal", "crackle", "normal", "crackle"]
    y_pred = ["normal", "crackle", "normal", "crackle"]

    reports = evaluate(y_true, y_pred, CLASSES)

    ausente = next(r for r in reports if r.detector == "both")
    assert ausente.support == 0
    assert ausente.precision is None
    assert ausente.recall is None
    assert ausente.f1 is None


def test_as_quatro_classes_aparecem_mesmo_com_support_zero():
    y_true = ["normal", "normal"]
    y_pred = ["normal", "normal"]

    reports = evaluate(y_true, y_pred, CLASSES)

    assert {r.detector for r in reports} == set(CLASSES)


def test_metricas_de_classe_com_acerto_parcial_batem_com_binary_metrics():
    y_true = ["crackle", "crackle", "normal", "wheeze"]
    y_pred = ["crackle", "normal", "normal", "wheeze"]

    reports = evaluate(y_true, y_pred, CLASSES)

    crackle = next(r for r in reports if r.detector == "crackle")
    assert crackle.precision == 1.0  # 1 tp, 0 fp
    assert crackle.recall == 0.5  # 1 tp, 1 fn
    assert crackle.support == 2


def test_save_evaluation_grava_json_valido_recarregavel(tmp_path):
    y_true = ["normal", "crackle", "wheeze", "both"]
    y_pred = ["normal", "crackle", "normal", "both"]
    reports = evaluate(y_true, y_pred, CLASSES)
    destino = tmp_path / "sub" / "metrics.json"

    save_evaluation(reports, destino)

    carregado = json.loads(destino.read_text(encoding="utf-8"))
    assert {item["detector"] for item in carregado} == set(CLASSES)
    for item in carregado:
        assert set(item) == {"detector", "precision", "recall", "f1", "support"}
