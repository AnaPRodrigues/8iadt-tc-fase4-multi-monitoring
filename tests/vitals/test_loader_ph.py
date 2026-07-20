"""Testes do parser de pH e da rotulagem de ground truth (VITALS-02).

O formato das linhas é o entregue pelo wfdb, que remove o '#' inicial do .hea:
o comentário `#pH           7.26` chega como `'pH           7.26'`.
"""

from vitals.loader import PH_THRESHOLD, is_pathological, parse_ph


def test_extrai_ph_normal():
    comments = ["-- Outcome measures", "pH           7.26", "BDecf        3.44"]

    assert parse_ph(comments) == 7.26


def test_extrai_ph_patologico():
    assert parse_ph(["pH           7.01"]) == 7.01


def test_tolera_espacamento_variavel():
    assert parse_ph(["pH 7.10"]) == 7.10
    assert parse_ph(["pH\t\t7.10"]) == 7.10


def test_comentario_de_ph_ausente_retorna_none():
    comments = ["-- Outcome measures", "BDecf        3.44", "Apgar1       8"]

    assert parse_ph(comments) is None


def test_lista_vazia_retorna_none():
    assert parse_ph([]) is None


def test_valor_nao_numerico_retorna_none():
    assert parse_ph(["pH           n/a"]) is None


def test_campo_diferente_que_contem_ph_nao_e_confundido():
    """`pCO2` e `pH_alt` não podem ser lidos como o campo `pH`."""
    assert parse_ph(["pCO2         6.8", "pH_alt       7.99"]) is None


def test_limiar_de_patologico_e_705():
    assert PH_THRESHOLD == 7.05


def test_ph_abaixo_do_limiar_e_patologico():
    assert is_pathological(7.04) is True


def test_ph_exatamente_no_limiar_nao_e_patologico():
    """Spec: patológico é `pH < 7.05` — 7.05 exato fica de fora."""
    assert is_pathological(7.05) is False


def test_ph_acima_do_limiar_nao_e_patologico():
    assert is_pathological(7.26) is False
