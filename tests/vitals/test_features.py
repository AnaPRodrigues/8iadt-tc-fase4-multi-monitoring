"""Testes de extração de features estatísticas e de domínio CTG."""

import numpy as np

from vitals.features import extract
from vitals.windowing import Window

FS = 4.0


def _janela(fhr: np.ndarray, *, insuficiente: bool = False) -> Window:
    return Window(
        record_id="0001",
        start_s=0.0,
        end_s=len(fhr) / FS,
        fhr=fhr,
        uc=np.full(len(fhr), 20.0),
        insufficient_data=insuficiente,
    )


def test_estatisticas_basicas_de_janela_normal():
    fhr = np.array([130.0, 140.0, 150.0, 140.0])

    f = extract(_janela(fhr), fs=FS)

    assert f.valid is True
    assert f.mean == 140.0
    assert f.min == 130.0
    assert f.max == 150.0
    assert f.std == np.std(fhr)


def test_janela_constante_tem_desvio_e_variabilidade_zero():
    f = extract(_janela(np.full(40, 140.0)), fs=FS)

    assert f.std == 0.0
    assert f.short_term_variability == 0.0
    assert f.baseline == 140.0


def test_baseline_resiste_a_desvio_pontual():
    """Baseline usa mediana: uma queda breve não deve arrastar o nível de referência."""
    fhr = np.full(100, 140.0)
    fhr[:10] = 90.0

    f = extract(_janela(fhr), fs=FS)

    assert f.baseline == 140.0


def test_variabilidade_de_curto_prazo_mede_diferenca_entre_amostras():
    fhr = np.array([140.0, 142.0, 140.0, 142.0])

    f = extract(_janela(fhr), fs=FS)

    assert f.short_term_variability == 2.0


def test_deceleracao_clinica_e_contada():
    """Queda >=15 bpm por >=15 s (64 amostras a 4 Hz) conta como uma deceleração."""
    fhr = np.full(480, 140.0)
    fhr[100:164] = 120.0

    f = extract(_janela(fhr), fs=FS)

    assert f.deceleration_count == 1


def test_queda_curta_demais_nao_conta_como_deceleracao():
    fhr = np.full(480, 140.0)
    fhr[100:132] = 120.0  # 8 s — abaixo do minimo clinico

    f = extract(_janela(fhr), fs=FS)

    assert f.deceleration_count == 0


def test_queda_rasa_demais_nao_conta_como_deceleracao():
    fhr = np.full(480, 140.0)
    fhr[100:200] = 132.0  # -8 bpm — abaixo do minimo clinico

    f = extract(_janela(fhr), fs=FS)

    assert f.deceleration_count == 0


def test_duas_deceleracoes_separadas_sao_contadas():
    fhr = np.full(480, 140.0)
    fhr[50:120] = 120.0
    fhr[300:370] = 118.0

    f = extract(_janela(fhr), fs=FS)

    assert f.deceleration_count == 2


def test_janela_insuficiente_e_marcada_e_nao_produz_numero_utilizavel():
    f = extract(_janela(np.full(40, 140.0), insuficiente=True), fs=FS)

    assert f.valid is False
    assert np.isnan(f.mean)
    assert np.isnan(f.baseline)
    assert np.isnan(np.asarray(f.to_array(), dtype=float)).all()


def test_valores_fisiologicamente_extremos_sao_preservados_sem_excecao():
    fhr = np.array([30.0, 240.0, 30.0, 240.0])

    f = extract(_janela(fhr), fs=FS)

    assert f.valid is True
    assert f.min == 30.0
    assert f.max == 240.0


def test_to_array_de_janela_valida_nao_tem_nan():
    f = extract(_janela(np.full(40, 140.0)), fs=FS)

    assert not np.isnan(np.asarray(f.to_array(), dtype=float)).any()
