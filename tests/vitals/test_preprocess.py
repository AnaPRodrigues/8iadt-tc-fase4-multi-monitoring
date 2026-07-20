"""Testes de preprocess — perda de sinal e gaps (mitigação do risco de dropout em CTG)."""

import numpy as np

from vitals.preprocess import interpolate_gaps, mark_signal_loss

FS = 4.0


def test_sinal_limpo_nao_tem_amostra_invalida():
    sinal = np.array([140.0, 141.0, 139.0, 140.0])

    assert not mark_signal_loss(sinal).any()


def test_zero_e_nan_sao_perda_de_sinal():
    sinal = np.array([140.0, 0.0, np.nan, 140.0])

    mask = mark_signal_loss(sinal)

    assert mask.tolist() == [False, True, True, False]


def test_gap_curto_e_interpolado_e_deixa_de_ser_invalido():
    sinal = np.array([140.0, 140.0, 0.0, 0.0, 150.0, 150.0])
    mask = mark_signal_loss(sinal)

    limpo, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=1.0, fs=FS)

    assert not nova_mask.any()
    # interpolação linear entre 140 (idx 1) e 150 (idx 4)
    assert limpo[2] == np.float64(140.0 + 10.0 / 3)
    assert limpo[3] == np.float64(140.0 + 20.0 / 3)


def test_gap_longo_permanece_invalido():
    sinal = np.concatenate([[140.0], np.zeros(10), [150.0]])
    mask = mark_signal_loss(sinal)

    _, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=1.0, fs=FS)

    assert nova_mask[1:11].all()
    assert not nova_mask[0]
    assert not nova_mask[11]


def test_gap_na_borda_inicial_nao_e_interpolado():
    """Sem âncora à esquerda não há o que interpolar — inventar valor seria fabricar dado."""
    sinal = np.array([0.0, 0.0, 140.0, 141.0])
    mask = mark_signal_loss(sinal)

    limpo, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=10.0, fs=FS)

    assert nova_mask[0] and nova_mask[1]
    assert limpo[0] == 0.0


def test_gap_na_borda_final_nao_e_interpolado():
    sinal = np.array([140.0, 141.0, 0.0, 0.0])
    mask = mark_signal_loss(sinal)

    _, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=10.0, fs=FS)

    assert nova_mask[2] and nova_mask[3]


def test_sinal_todo_perdido_nao_interpola_nada():
    sinal = np.zeros(8)
    mask = mark_signal_loss(sinal)

    limpo, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=10.0, fs=FS)

    assert nova_mask.all()
    assert np.array_equal(limpo, sinal)


def test_sinal_vazio_nao_quebra():
    sinal = np.array([])
    mask = mark_signal_loss(sinal)

    limpo, nova_mask = interpolate_gaps(sinal, mask, max_gap_s=1.0, fs=FS)

    assert limpo.size == 0
    assert nova_mask.size == 0


def test_entrada_original_nao_e_mutada():
    sinal = np.array([140.0, 0.0, 150.0])
    mask = mark_signal_loss(sinal)

    interpolate_gaps(sinal, mask, max_gap_s=10.0, fs=FS)

    assert sinal[1] == 0.0
