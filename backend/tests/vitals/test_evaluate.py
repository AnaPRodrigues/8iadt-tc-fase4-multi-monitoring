"""Testes da avaliação contra o rótulo pH real (VITALS-06, VITALS-10)."""

import numpy as np
import pytest

from pipelines.vitals.aggregate import RecordVerdict
from pipelines.vitals.evaluate import evaluate
from pipelines.vitals.loader import Segment, VitalRecord


def _registro(record_id: str, ph: float) -> VitalRecord:
    return VitalRecord(
        record_id=record_id,
        fhr=np.full(8, 140.0),
        uc=np.full(8, 20.0),
        fs=4.0,
        ph=ph,
        provenance=[Segment(record_id, 0, 8)],
    )


def _veredicto(record_id: str, patologico: bool | None) -> RecordVerdict:
    return RecordVerdict(
        record_id=record_id,
        predicted_pathological=patologico,
        anomalous_fraction=None if patologico is None else 0.5,
        n_windows_valid=0 if patologico is None else 10,
        n_windows_excluded=0,
    )


def test_conjunto_misto_calcula_metricas_por_detector():
    registros = [_registro("a", 7.01), _registro("b", 7.30), _registro("c", 7.02)]
    verdicts = {
        "zscore": [_veredicto("a", True), _veredicto("b", False), _veredicto("c", True)],
        "iforest": [_veredicto("a", True), _veredicto("b", True), _veredicto("c", False)],
    }

    rel = evaluate(verdicts, registros)

    z = next(m for m in rel.metrics if m.detector == "zscore")
    assert z.precision == 1.0
    assert z.recall == 1.0
    assert z.support == 2

    i = next(m for m in rel.metrics if m.detector == "iforest")
    assert i.precision == pytest.approx(0.5)
    assert i.recall == pytest.approx(0.5)


def test_prevalencia_real_e_reportada():
    registros = [_registro("a", 7.01), _registro("b", 7.30), _registro("c", 7.30)]
    verdicts = {"zscore": [_veredicto("a", True), _veredicto("b", False), _veredicto("c", False)]}

    rel = evaluate(verdicts, registros)

    assert rel.prevalence == pytest.approx(1 / 3)
    assert rel.n_pathological == 1
    assert rel.n_records == 3


def test_conjunto_sem_patologico_avisa_que_recall_e_indefinido(caplog):
    """VITALS-10: avisar explicitamente em vez de reportar recall zero sem contexto."""
    registros = [_registro("a", 7.30), _registro("b", 7.40)]
    verdicts = {"zscore": [_veredicto("a", False), _veredicto("b", True)]}

    with caplog.at_level("WARNING", logger="mm.vitals.evaluate"):
        rel = evaluate(verdicts, registros)

    assert rel.prevalence == 0.0
    assert next(m for m in rel.metrics if m.detector == "zscore").recall is None
    assert "recall" in caplog.text.lower()


def test_conjunto_so_patologico_reporta_prevalencia_total():
    registros = [_registro("a", 7.01), _registro("b", 7.02)]
    verdicts = {"zscore": [_veredicto("a", True), _veredicto("b", True)]}

    rel = evaluate(verdicts, registros)

    assert rel.prevalence == 1.0
    assert next(m for m in rel.metrics if m.detector == "zscore").recall == 1.0


def test_veredicto_indeterminado_e_excluido_do_calculo():
    """Registro sem janela válida não pode contar como acerto nem como erro."""
    registros = [_registro("a", 7.01), _registro("b", 7.30), _registro("c", 7.02)]
    verdicts = {"zscore": [_veredicto("a", True), _veredicto("b", False), _veredicto("c", None)]}

    rel = evaluate(verdicts, registros)

    assert rel.n_excluded == 1
    m = next(m for m in rel.metrics if m.detector == "zscore")
    assert m.support == 1  # apenas "a" entrou como positivo real
    assert m.recall == 1.0


def test_registro_sem_veredicto_correspondente_e_ignorado():
    registros = [_registro("a", 7.01), _registro("b", 7.30)]
    verdicts = {"zscore": [_veredicto("a", True)]}

    rel = evaluate(verdicts, registros)

    assert next(m for m in rel.metrics if m.detector == "zscore").support == 1


def test_conjunto_vazio_nao_quebra():
    rel = evaluate({"zscore": []}, [])

    assert rel.prevalence is None
    assert rel.n_records == 0
    assert next(m for m in rel.metrics if m.detector == "zscore").precision is None
