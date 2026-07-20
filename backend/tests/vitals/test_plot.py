"""Testes do gráfico de evidência da janela anômala (VITALS-06, AD-026)."""

import numpy as np
import pytest

from pipelines.vitals.detectors import AnomalyEvent
from pipelines.vitals.loader import Segment, VitalRecord
from pipelines.vitals.plot import plot_anomaly_window, titulo_evidencia

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


def _titulo(**over) -> str:
    """Monta o título variando um campo por vez."""
    registro = VitalRecord(
        record_id=over.get("record_id", "1464"),
        fhr=np.full(200, 140.0),
        uc=np.full(200, 20.0),
        fs=FS,
        ph=over.get("ph", 7.01),
        provenance=[Segment(over.get("record_id", "1464"), 0, 200)],
    )
    evento = AnomalyEvent(
        record_id=over.get("record_id", "1464"),
        detector=over.get("detector", "zscore"),
        start_s=over.get("start_s", 10.0),
        end_s=over.get("end_s", 12.0),
        score=over.get("score", 3.70),
        source_record_id=over.get("record_id", "1464"),
    )
    return titulo_evidencia(registro, evento)


@pytest.mark.parametrize(
    ("campo", "a", "b", "texto_a", "texto_b"),
    [
        ("record_id", "1464", "2001", "1464", "2001"),
        ("detector", "zscore", "isolation_forest", "zscore", "isolation_forest"),
        ("ph", 7.01, 7.31, "7.01", "7.31"),
        ("score", 3.70, 8.25, "3.70", "8.25"),
        ("start_s", 10.0, 44.0, "10.0", "44.0"),
        ("end_s", 12.0, 57.0, "12.0", "57.0"),
    ],
)
def test_cada_campo_do_titulo_reflete_o_valor_do_evento(campo, a, b, texto_a, texto_b):
    """Cada campo precisa VARIAR com o evento, não ser constante.

    Asserir só presença de substring contra uma fixture de literais fixos deixa
    qualquer campo ser substituído por uma constante sem que nada quebre — foi
    assim que o `detector` do título passou despercebido por quatro rodadas.
    """
    titulo_a = _titulo(**{campo: a})
    titulo_b = _titulo(**{campo: b})

    assert texto_a in titulo_a and texto_b not in titulo_a
    assert texto_b in titulo_b and texto_a not in titulo_b


def test_titulo_mostra_a_janela_completa_do_evento():
    t = _titulo(start_s=10.0, end_s=12.0)

    assert "10.0" in t
    assert "12.0" in t


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
