"""Testes de janelamento deslizante (VITALS-09, ordem cronológica)."""

import numpy as np

from vitals.loader import Segment, VitalRecord
from vitals.windowing import make_windows

FS = 4.0


def _registro(n: int = 20) -> VitalRecord:
    return VitalRecord(
        record_id="0001",
        fhr=np.full(n, 140.0),
        uc=np.full(n, 20.0),
        fs=FS,
        ph=7.26,
        provenance=[Segment("0001", 0, n)],
    )


def test_janelamento_regular_gera_janelas_completas():
    r = _registro(20)
    mask = np.zeros(20, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=1.0, mask=mask)

    assert len(janelas) == 4
    assert [j.start_s for j in janelas] == [0.0, 1.0, 2.0, 3.0]
    assert [j.end_s for j in janelas] == [2.0, 3.0, 4.0, 5.0]
    assert all(j.fhr.size == 8 for j in janelas)


def test_stride_menor_que_janela_produz_sobreposicao():
    r = _registro(20)
    mask = np.zeros(20, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=1.0, mask=mask)

    assert janelas[0].end_s > janelas[1].start_s


def test_janela_final_incompleta_e_descartada():
    """Janela mais curta teria suporte amostral diferente e distorceria a comparação."""
    r = _registro(22)
    mask = np.zeros(22, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=1.0, mask=mask)

    assert janelas[-1].end_s == 5.0
    assert all(j.fhr.size == 8 for j in janelas)


def test_serie_mais_curta_que_a_janela_retorna_lista_vazia():
    r = _registro(4)
    mask = np.zeros(4, dtype=bool)

    assert make_windows(r, size_s=2.0, stride_s=1.0, mask=mask) == []


def test_janela_com_invalidos_acima_do_limite_e_marcada_insuficiente():
    r = _registro(8)
    mask = np.zeros(8, dtype=bool)
    mask[:6] = True  # 75% inválido

    janelas = make_windows(r, size_s=2.0, stride_s=2.0, mask=mask, max_invalid_fraction=0.5)

    assert len(janelas) == 1
    assert janelas[0].insufficient_data is True


def test_janela_com_invalidos_abaixo_do_limite_permanece_valida():
    r = _registro(8)
    mask = np.zeros(8, dtype=bool)
    mask[:2] = True  # 25% inválido

    janelas = make_windows(r, size_s=2.0, stride_s=2.0, mask=mask, max_invalid_fraction=0.5)

    assert janelas[0].insufficient_data is False


def test_janela_totalmente_invalida_e_insuficiente():
    r = _registro(8)
    mask = np.ones(8, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=2.0, mask=mask)

    assert janelas[0].insufficient_data is True


def test_ordem_cronologica_e_estritamente_crescente():
    r = _registro(40)
    mask = np.zeros(40, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=1.0, mask=mask)
    inicios = [j.start_s for j in janelas]

    assert inicios == sorted(inicios)
    assert len(set(inicios)) == len(inicios)


def test_janela_carrega_o_record_id_de_origem():
    r = _registro(8)
    mask = np.zeros(8, dtype=bool)

    janelas = make_windows(r, size_s=2.0, stride_s=2.0, mask=mask)

    assert janelas[0].record_id == "0001"
