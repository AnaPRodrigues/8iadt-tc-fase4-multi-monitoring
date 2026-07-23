"""Testes da agregação janela → registro."""

import pytest

from pipelines.vitals.aggregate import aggregate


def _flags(n_anomalas: int, n_normais: int, n_invalidas: int = 0) -> list[bool | None]:
    return [True] * n_anomalas + [False] * n_normais + [None] * n_invalidas


def test_fracao_acima_de_tau_classifica_como_patologico():
    v = aggregate("0001", _flags(3, 7), tau=0.2)

    assert v.anomalous_fraction == pytest.approx(0.3)
    assert v.predicted_pathological is True


def test_fracao_abaixo_de_tau_nao_classifica_como_patologico():
    v = aggregate("0001", _flags(1, 9), tau=0.2)

    assert v.anomalous_fraction == pytest.approx(0.1)
    assert v.predicted_pathological is False


def test_fracao_exatamente_igual_a_tau_nao_e_patologico():
    """A regra de agregação define `> tau`, estritamente — a fronteira fica de fora."""
    v = aggregate("0001", _flags(2, 8), tau=0.2)

    assert v.anomalous_fraction == pytest.approx(0.2)
    assert v.predicted_pathological is False


def test_tau_default_e_015():
    # 2 de 10 = 0.2 > 0.15 (default de tau)
    v = aggregate("0001", _flags(2, 8))

    assert v.predicted_pathological is True


def test_janelas_invalidas_ficam_fora_do_denominador():
    """Janela insuficiente não pode ser contada como normal."""
    v = aggregate("0001", _flags(3, 7, n_invalidas=90), tau=0.2)

    assert v.n_windows_valid == 10
    assert v.n_windows_excluded == 90
    assert v.anomalous_fraction == pytest.approx(0.3)
    assert v.predicted_pathological is True


def test_registro_sem_janela_valida_fica_indeterminado():
    v = aggregate("0001", _flags(0, 0, n_invalidas=5), tau=0.2)

    assert v.predicted_pathological is None
    assert v.anomalous_fraction is None
    assert v.n_windows_valid == 0
    assert v.n_windows_excluded == 5


def test_lista_vazia_fica_indeterminada():
    v = aggregate("0001", [], tau=0.2)

    assert v.predicted_pathological is None
    assert v.n_windows_valid == 0


def test_todas_as_janelas_anomalas():
    v = aggregate("0001", _flags(5, 0), tau=0.2)

    assert v.anomalous_fraction == 1.0
    assert v.predicted_pathological is True


def test_veredicto_carrega_o_record_id():
    assert aggregate("1464", _flags(1, 9)).record_id == "1464"


def test_tau_fora_do_intervalo_valido_e_rejeitado():
    with pytest.raises(ValueError, match="tau"):
        aggregate("0001", _flags(1, 9), tau=1.5)
