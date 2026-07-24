"""Testes do segundo caso de sinais vitais (BIDMC — internação adulta).

- Unitários: critérios clínicos de referência e cálculo de métricas (sem dados).
- Integração: leitura de registro numérico real, análise (HR/SpO2) e varredura;
  pulam com mensagem clara se o dataset não estiver presente (`make data`).
"""

from pathlib import Path

import numpy as np
import pytest

from pipelines.vitals import bidmc

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BIDMC = _REPO_ROOT / "data" / "bidmc"


# --------------------------------------------------------------------------- #
# Unitários — critérios clínicos e métricas (sem dataset)
# --------------------------------------------------------------------------- #
def test_hr_fora_da_faixa_e_anomala():
    crit = bidmc.CRITERIOS_CLINICOS
    assert bidmc._hr_anomala(np.full(60, 120.0), crit) is True  # taquicardia
    assert bidmc._hr_anomala(np.full(60, 45.0), crit) is True  # bradicardia
    assert bidmc._hr_anomala(np.full(60, 75.0), crit) is False  # normal


def test_spo2_sustentada_abaixo_de_90_e_anomala():
    crit = bidmc.CRITERIOS_CLINICOS
    assert bidmc._spo2_anomala(np.full(60, 85.0), crit) is True  # hipoxemia sustentada
    assert bidmc._spo2_anomala(np.full(60, 97.0), crit) is False  # normal


def test_spo2_queda_pontual_nao_e_sustentada():
    crit = bidmc.CRITERIOS_CLINICOS
    janela = np.full(60, 97.0)
    janela[:5] = 80.0  # só 5 de 60 amostras baixas -> não sustentado
    assert bidmc._spo2_anomala(janela, crit) is False


def test_metricas_precision_recall_f1():
    precision, recall, f1 = bidmc._metricas([True, True, False], [True, False, False])
    assert precision == 0.5
    assert recall == 1.0
    assert f1 == pytest.approx(2 / 3, abs=1e-3)


# --------------------------------------------------------------------------- #
# Integração — dataset BIDMC real
# --------------------------------------------------------------------------- #
def _skip_se_ausente():
    if not _BIDMC.is_dir() or not list(_BIDMC.glob("*n.hea")):
        pytest.skip("dataset BIDMC ausente — rode `make data`")


@pytest.mark.integration
def test_le_registro_numerico_expondo_hr_e_spo2_a_1hz():
    _skip_se_ausente()
    record = bidmc.load_numeric_record(_BIDMC / "bidmc01n")

    assert record.fs == 1.0
    assert len(record.hr) > 0
    assert len(record.spo2) == len(record.hr)


@pytest.mark.integration
def test_registro_com_hipoxemia_produz_resumo_clinico_e_evidencia(tmp_path, monkeypatch):
    _skip_se_ausente()
    if not (_BIDMC / "bidmc32n.hea").is_file():
        pytest.skip("registro bidmc32n (com evento de SpO2) ausente")
    monkeypatch.chdir(tmp_path)
    record = bidmc.load_numeric_record(_BIDMC / "bidmc32n")

    achado = bidmc.analisar(record, run_id="teste", root=tmp_path / "output")

    assert achado.pontuacao == 1.0
    assert "saturação" in achado.resumo.lower()
    assert "90%" in achado.resumo
    assert achado.evidencia_id is not None
    assert achado.evidencia.artifact_path.is_file()  # gráfico gerado


@pytest.mark.integration
def test_registro_sem_evento_reporta_sem_alteracoes(tmp_path):
    _skip_se_ausente()
    record = bidmc.load_numeric_record(_BIDMC / "bidmc01n")

    achado = bidmc.analisar(record, run_id="teste", root=tmp_path / "output")

    assert achado.pontuacao == 0.0
    assert achado.evidencia_id is None


@pytest.mark.integration
def test_varredura_lista_registros_com_eventos():
    _skip_se_ausente()
    achados = bidmc.varrer(_BIDMC)

    assert len(achados) > 0
    # pelo menos um registro tem evento clínico (a varredura serve p/ escolher casos)
    assert any(a.eventos_hr or a.eventos_spo2 for a in achados)
