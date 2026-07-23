"""Testes da construção do evento de anomalia.

Estes testes existem porque asserir o payload só no teste de integração é fraco:
lá não há como recomputar o score esperado, então uma troca de valor passa
despercebida. Aqui a fidelidade de cada campo é verificável diretamente.
"""

import numpy as np
import pytest

from pipelines.vitals.cli import build_event, evidence_id_de
from pipelines.vitals.loader import Segment, VitalRecord
from pipelines.vitals.windowing import Window

FS = 4.0


def _registro(record_id="1464", provenance=None) -> VitalRecord:
    n = 400
    return VitalRecord(
        record_id=record_id,
        fhr=np.full(n, 140.0),
        uc=np.full(n, 20.0),
        fs=FS,
        ph=7.01,
        provenance=provenance or [Segment(record_id, 0, n)],
    )


def _janela(start_s=10.0, end_s=30.0) -> Window:
    return Window(
        record_id="1464",
        start_s=start_s,
        end_s=end_s,
        fhr=np.full(80, 140.0),
        uc=np.full(80, 20.0),
        insufficient_data=False,
    )


@pytest.mark.parametrize("score", [3.7, 0.0, 99.0, -1.5])
def test_score_e_preservado_exatamente(score):
    """Qualquer alteração do valor entre detector e evidência é um bug."""
    ev = build_event(_registro(), "zscore", _janela(), score)

    assert ev.score == pytest.approx(score)


@pytest.mark.parametrize("nome", ["zscore", "isolation_forest"])
def test_detector_e_preservado_exatamente(nome):
    """Rotular a evidência com o detector errado invalidaria as métricas por detector."""
    ev = build_event(_registro(), nome, _janela(), 3.7)

    assert ev.detector == nome


def test_janela_e_preservada():
    ev = build_event(_registro(), "zscore", _janela(start_s=12.0, end_s=32.0), 3.7)

    assert ev.start_s == 12.0
    assert ev.end_s == 32.0


def test_proveniencia_de_registro_simples_e_o_proprio_registro():
    ev = build_event(_registro(), "zscore", _janela(), 3.7)

    assert ev.source_record_id == "1464"


def test_proveniencia_em_timeline_aponta_o_trecho_correto():
    r = _registro(
        record_id="timeline-demo",
        provenance=[Segment("normal01", 0, 200), Segment("patol01", 200, 400)],
    )

    cedo = build_event(r, "zscore", _janela(start_s=10.0, end_s=30.0), 3.7)
    tarde = build_event(r, "zscore", _janela(start_s=60.0, end_s=80.0), 3.7)

    assert cedo.source_record_id == "normal01"
    assert tarde.source_record_id == "patol01"


def test_evidence_id_deriva_do_evento_e_carrega_o_detector():
    ev = build_event(_registro(), "isolation_forest", _janela(start_s=12.0), 3.7)

    assert evidence_id_de(ev) == "1464-isolation_forest-12s"


def test_evidence_ids_de_detectores_diferentes_nao_colidem():
    janela = _janela()
    a = evidence_id_de(build_event(_registro(), "zscore", janela, 3.7))
    b = evidence_id_de(build_event(_registro(), "isolation_forest", janela, 3.7))

    assert a != b
