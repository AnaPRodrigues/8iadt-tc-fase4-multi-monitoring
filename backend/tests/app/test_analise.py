"""Testes do despacho de análise (composição dos pipelines sobre um arquivo).

- Documento: rápido, com PDF sintético gerado (sem conjunto de dados externo).
- Vídeo / sinais vitais: integração contra os conjuntos de dados reais; pulam com
  mensagem clara se o dataset não estiver presente (`make data`).
"""

from pathlib import Path

import pytest

from app import analise
from pipelines.prescription.generator import generate_prescription
from pipelines.prescription.models import PrescriptionRecord

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _modo_local(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.chdir(tmp_path)  # evidência (output/) não polui o repo


# --------------------------------------------------------------------------- #
# Documento (unitário — PDF gerado)
# --------------------------------------------------------------------------- #
def test_documento_sem_anomalia_resume_sem_alerta(tmp_path):
    pdf = tmp_path / "presc.pdf"
    pdf.write_bytes(generate_prescription("p-1", "losartana", 50, "1x/dia", seed=1))

    r = analise._analisar_documento(pdf, prescricao_anterior=None)

    assert r.pontuacao == 0.0
    assert "Losartana" in r.resumo
    assert "sem alteração" in r.resumo.lower()


def test_documento_variacao_abrupta_vira_resumo_clinico(tmp_path):
    pdf = tmp_path / "presc.pdf"
    pdf.write_bytes(generate_prescription("p-1", "losartana", 100, "1x/dia", seed=2))
    anterior = PrescriptionRecord("p-1", "losartana", 50.0, "mg", "1x/dia", "2026-01-01T00:00:00")

    r = analise._analisar_documento(pdf, prescricao_anterior=anterior)

    assert r.pontuacao == 1.0
    assert "100%" in r.resumo  # variação relativa em linguagem clínica
    assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Vídeo (integração — sequência URFD real)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_video_sequencia_de_queda_real_produz_resumo_e_evidencia(tmp_path):
    seq = _REPO_ROOT / "data" / "urfd" / "fall-23"
    if not seq.is_dir():
        pytest.skip("dataset URFD ausente — rode `make data`")

    r = analise._analisar_video(seq, run_id="teste-video")

    assert r.pontuacao in (0.0, 1.0)
    assert r.resumo  # sempre há um resumo em linguagem clínica
    if r.pontuacao == 1.0:
        assert "queda" in r.resumo.lower()
        assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Sinais vitais (integração — registro CTU-UHB real)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_sinais_vitais_registro_real_produz_resumo(tmp_path):
    ctu = _REPO_ROOT / "data" / "ctu-uhb"
    if not ctu.is_dir():
        pytest.skip("dataset CTU-UHB ausente — rode `make data`")
    heas = sorted(ctu.glob("*.hea"))
    if not heas:
        pytest.skip("nenhum registro CTU-UHB encontrado")

    r = analise._analisar_sinais_vitais(heas[0], run_id="teste-vitais")

    assert r.resumo
    assert r.pontuacao in (0.0, 1.0)
    if r.pontuacao == 1.0:
        assert "frequência cardíaca" in r.resumo.lower()
        assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Áudio (integração — gravação ICBHI real; treina o classificador sob demanda)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_sinais_vitais_roteia_bidmc_para_o_caso_de_internacao(tmp_path):
    bidmc = _REPO_ROOT / "data" / "bidmc"
    if not (bidmc / "bidmc32n.hea").is_file():
        pytest.skip("registro BIDMC ausente — rode `make data`")

    # o despacho reconhece o registro pelos canais (HR/SpO2) e roteia p/ internação
    r = analise._analisar_sinais_vitais(bidmc / "bidmc32n.hea", run_id="teste-internacao")

    assert r.detalhes.get("caso") == "internacao"
    assert r.resumo
    if r.pontuacao == 1.0:
        assert r.evidencia_id is not None


@pytest.mark.integration
def test_audio_gravacao_real_produz_resumo_respiratorio(tmp_path, monkeypatch):
    icbhi = _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"
    if not icbhi.is_dir():
        pytest.skip("dataset ICBHI ausente — rode `make data`")
    wavs = sorted(icbhi.glob("*.wav"))
    if not wavs:
        pytest.skip("nenhuma gravação ICBHI encontrada")

    r = analise._analisar_audio(wavs[0], run_id="teste-audio", dataset_icbhi=icbhi, seed=42)

    assert r.resumo
    # pontuação é a confiança do classificador (0.0 quando não há alteração)
    assert r.pontuacao is None or 0.0 <= r.pontuacao <= 1.0
