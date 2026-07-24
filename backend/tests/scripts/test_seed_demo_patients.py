"""Testes do script de carga de pacientes de demonstração.

- Unitários: idempotência do "já existe, pula" (paciente e envios), com a
  análise substituída por um dublê — rápidos, sem dataset.
- Integração: roda a carga real duas vezes contra os datasets já baixados e
  confirma que a segunda vez não duplica nada; pula com mensagem clara se os
  datasets não estiverem presentes.
"""

from pathlib import Path

import pytest

from app import repositorio
from scripts import seed_demo_patients as seed

_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _ambiente_isolado(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("APP_UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.chdir(tmp_path)  # evidência (output/) não polui o repo


def test_garantir_paciente_nao_duplica_ao_rodar_de_novo():
    a = seed._garantir_paciente("Paciente X", "obs")
    b = seed._garantir_paciente("Paciente X", "obs")

    assert a.id == b.id
    assert len(repositorio.listar_pacientes()) == 1


def test_paciente_com_envios_e_pulado_sem_reanalisar(monkeypatch):
    paciente = repositorio.criar_paciente("Paciente A — Queda e Monitoramento Fetal")
    repositorio.criar_upload(paciente.id, "video", "/x", "x")  # simula envio já feito

    def _falha_se_chamado(*_args, **_kwargs):
        raise AssertionError("não deveria reanalisar um paciente que já tem envios")

    monkeypatch.setattr(seed, "_enviar_e_analisar", _falha_se_chamado)

    seed._paciente_queda_e_ctg()  # não deve levantar nem acessar dataset nenhum

    assert len(repositorio.listar_uploads(paciente.id)) == 1  # continua só o simulado


@pytest.mark.integration
def test_main_roda_duas_vezes_sem_duplicar_pacientes_ou_envios():
    datasets = [
        _REPO_ROOT / "data" / "urfd" / "fall-01",
        _REPO_ROOT / "data" / "ctu-uhb" / "1001.hea",
        _REPO_ROOT / "data" / "endoscapes" / "endoscapes" / "test" / "168_24925.jpg",
        _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database" / "114_1b4_Al_mc_AKGC417L.wav",
        _REPO_ROOT / "data" / "bidmc" / "bidmc32n.hea",
    ]
    if not all(p.exists() for p in datasets):
        pytest.skip("datasets da demo ausentes — rode `make data`")

    seed.main()
    pacientes_1 = repositorio.listar_pacientes()
    uploads_1 = sum(len(repositorio.listar_uploads(p.id)) for p in pacientes_1)

    seed.main()
    pacientes_2 = repositorio.listar_pacientes()
    uploads_2 = sum(len(repositorio.listar_uploads(p.id)) for p in pacientes_2)

    assert len(pacientes_1) == 3
    assert pacientes_1 == pacientes_2  # mesmos registros, nada recriado
    assert uploads_1 == uploads_2 > 0
