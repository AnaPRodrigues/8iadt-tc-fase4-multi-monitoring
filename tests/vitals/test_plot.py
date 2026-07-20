"""Testes do gráfico de evidência da janela anômala (VITALS-06, AD-026)."""

import numpy as np

from vitals.detectors import AnomalyEvent
from vitals.loader import Segment, VitalRecord
from vitals.plot import plot_anomaly_window, titulo_evidencia

FS = 4.0


def _registro(n: int = 200, ph: float = 7.01) -> VitalRecord:
    return VitalRecord(
        record_id="1464",
        fhr=np.full(n, 140.0),
        uc=np.full(n, 20.0),
        fs=FS,
        ph=ph,
        provenance=[Segment("1464", 0, n)],
    )


def _evento(start_s: float, end_s: float) -> AnomalyEvent:
    return AnomalyEvent(
        record_id="1464",
        detector="zscore",
        start_s=start_s,
        end_s=end_s,
        score=3.7,
        source_record_id="1464",
    )


def test_gera_o_arquivo_de_grafico(tmp_path):
    destino = tmp_path / "ev.png"

    caminho = plot_anomaly_window(_registro(), _evento(10.0, 12.0), destino)

    assert caminho == destino
    assert destino.is_file()
    assert destino.stat().st_size > 0


def test_titulo_identifica_registro_ph_e_detector():
    t = titulo_evidencia(_registro(ph=7.01), _evento(10.0, 12.0))

    assert "1464" in t
    assert "7.01" in t
    assert "zscore" in t


def test_titulo_mostra_o_score_e_a_janela_do_evento():
    """Um gráfico que anuncia score ou janela errados é evidência enganosa."""
    t = titulo_evidencia(_registro(), _evento(10.0, 12.0))

    assert "3.70" in t
    assert "10.0" in t
    assert "12.0" in t


def test_titulo_reflete_score_diferente():
    """Vizinho do caso acima: o título precisa variar com o score, não ser fixo."""
    evento = AnomalyEvent(
        record_id="1464",
        detector="zscore",
        start_s=10.0,
        end_s=12.0,
        score=8.25,
        source_record_id="1464",
    )

    t = titulo_evidencia(_registro(), evento)

    assert "8.25" in t
    assert "3.70" not in t


def test_titulo_mostra_proveniencia_quando_difere_do_registro():
    """Na timeline composta, a evidência precisa dizer de qual registro real veio."""
    evento = AnomalyEvent(
        record_id="timeline-demo",
        detector="zscore",
        start_s=10.0,
        end_s=12.0,
        score=3.7,
        source_record_id="1001",
    )

    t = titulo_evidencia(_registro(), evento)

    assert "1001" in t


def test_janela_no_inicio_da_serie_nao_quebra(tmp_path):
    destino = tmp_path / "borda-inicio.png"

    plot_anomaly_window(_registro(), _evento(0.0, 2.0), destino)

    assert destino.is_file()


def test_janela_no_fim_da_serie_nao_quebra(tmp_path):
    r = _registro(200)
    fim = len(r.fhr) / FS
    destino = tmp_path / "borda-fim.png"

    plot_anomaly_window(r, _evento(fim - 2.0, fim), destino)

    assert destino.is_file()


def test_cria_diretorio_inexistente(tmp_path):
    destino = tmp_path / "novo" / "dir" / "ev.png"

    plot_anomaly_window(_registro(), _evento(10.0, 12.0), destino)

    assert destino.is_file()
