"""Carga inicial de pacientes de demonstração.

Cria pacientes reais no banco local (SQLite) e vincula a cada um arquivos reais
dos conjuntos de dados já baixados (`make data`), mais uma prescrição sintética
com dose fora da faixa terapêutica (única fonte sem dataset aberto viável, ver
`pipelines/prescription/generator.py`). Cada envio passa pela análise real —
mesma composição dos pipelines que o endpoint HTTP usa (`servico.analisar_upload`)
— populando o banco, a linha do tempo de risco e os alertas de verdade.

Idempotente: roda de novo sem duplicar — um paciente com o mesmo nome já
cadastrado é reaproveitado, não recriado.

Uso: ``make seed-demo`` (equivalente a ``PYTHONPATH=backend python -m
scripts.seed_demo_patients``). Requer os datasets baixados (`make data`); a
raia cirúrgica de vídeo também requer os pesos do detector (`make
models-fetch`) — sem eles, esse envio específico fica marcado como "erro"
(comportamento já existente do despacho de análise), o resto da carga segue.
"""

from pathlib import Path

from app import armazenamento, repositorio, servico
from pipelines.prescription import catalog, generator

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA = _REPO_ROOT / "data"


def _paciente_existente(nome: str) -> repositorio.Paciente | None:
    return next((p for p in repositorio.listar_pacientes() if p.nome == nome), None)


def _garantir_paciente(nome: str, observacoes: str) -> repositorio.Paciente:
    existente = _paciente_existente(nome)
    if existente is not None:
        print(f"  paciente já existe, reaproveitando: {nome} ({existente.id})")
        return existente
    paciente = repositorio.criar_paciente(nome, observacoes=observacoes)
    print(f"  paciente criado: {nome} ({paciente.id})")
    return paciente


def _enviar_arquivo(
    paciente: repositorio.Paciente, modalidade: str, caminho: Path
) -> repositorio.Upload:
    return repositorio.criar_upload(paciente.id, modalidade, str(caminho), Path(caminho).name)


def _enviar_e_analisar(
    paciente: repositorio.Paciente, modalidade: str, caminho: Path, instante_s: float
) -> None:
    upload = _enviar_arquivo(paciente, modalidade, caminho)
    analise = servico.analisar_upload(upload.id, instante_s=instante_s)
    print(f"    {modalidade}: {analise.resultado.get('resumo', '(sem resumo)')}")


def _copiar_par(paciente_id: str, modalidade: str, principal: Path, irmao: Path) -> Path:
    """Copia dois arquivos que compartilham o mesmo nome-base (ex.: .hea/.dat de
    um registro wfdb; .wav/.txt de uma gravação ICBHI) para o mesmo diretório de
    envio, devolvendo o caminho do arquivo principal (o que a análise espera)."""
    destino_principal = armazenamento.copiar_arquivo(paciente_id, modalidade, principal)
    armazenamento.copiar_arquivo(paciente_id, modalidade, irmao)
    return destino_principal


# --------------------------------------------------------------------------- #
# Paciente A — queda (URFD) + cardiotocografia (CTU-UHB)
# --------------------------------------------------------------------------- #
def _paciente_queda_e_ctg() -> None:
    print("Paciente A — queda e monitoramento fetal")
    paciente = _garantir_paciente(
        "Paciente A — Queda e Monitoramento Fetal",
        "Demonstração: postura/queda (UR Fall Detection) + cardiotocografia (CTU-UHB).",
    )
    if repositorio.listar_uploads(paciente.id):
        print("  já tem envios, pulando")
        return

    sequencia = _DATA / "urfd" / "fall-01"
    if sequencia.is_dir():
        destino = armazenamento.copiar_diretorio(paciente.id, "video", sequencia)
        _enviar_e_analisar(paciente, "video", destino, instante_s=0.0)
    else:
        print("  URFD (fall-01) ausente — rode `make data`")

    ctg = _DATA / "ctu-uhb" / "1001.hea"
    if ctg.is_file():
        destino = _copiar_par(paciente.id, "sinais_vitais", ctg, ctg.with_suffix(".dat"))
        _enviar_e_analisar(paciente, "sinais_vitais", destino, instante_s=300.0)
    else:
        print("  CTU-UHB (1001) ausente — rode `make data`")


# --------------------------------------------------------------------------- #
# Paciente B — quadro cirúrgico (Endoscapes) + prescrição anômala (sintética)
# --------------------------------------------------------------------------- #
def _paciente_cirurgia_e_prescricao() -> None:
    print("Paciente B — cirurgia e prescrição")
    paciente = _garantir_paciente(
        "Paciente B — Pós-operatório e Prescrição",
        "Demonstração: estrutura crítica cirúrgica (Endoscapes) + prescrição "
        "sintética com dose fora da faixa terapêutica.",
    )
    if repositorio.listar_uploads(paciente.id):
        print("  já tem envios, pulando")
        return

    quadro = _DATA / "endoscapes" / "endoscapes" / "test" / "168_24925.jpg"
    if quadro.is_file():
        destino = armazenamento.copiar_arquivo(paciente.id, "video", quadro)
        _enviar_e_analisar(paciente, "video", destino, instante_s=0.0)
    else:
        print("  Endoscapes ausente — rode `make data`")

    faixa = catalog.lookup("digoxina")
    dose_anomala = round(faixa.max_dose * 3, 3)  # bem acima da faixa (0,5mg -> 1,5mg)
    pdf_bytes = generator.generate_prescription(
        patient_id=paciente.id, drug="digoxina", dose=dose_anomala, frequency="1x/dia", seed=1
    )
    caminho = armazenamento.salvar_arquivo(
        paciente.id, "documento", "prescricao_digoxina.pdf", pdf_bytes
    )
    _enviar_e_analisar(paciente, "documento", caminho, instante_s=600.0)


# --------------------------------------------------------------------------- #
# Paciente C — ausculta respiratória (ICBHI) + internação (BIDMC)
# --------------------------------------------------------------------------- #
def _paciente_respiracao_e_internacao() -> None:
    print("Paciente C — ausculta e internação")
    paciente = _garantir_paciente(
        "Paciente C — Ausculta Respiratória e Internação",
        "Demonstração: dificuldade respiratória (ICBHI) + oxigenação/HR de "
        "internação adulta (BIDMC).",
    )
    if repositorio.listar_uploads(paciente.id):
        print("  já tem envios, pulando")
        return

    gravacao = _DATA / "icbhi" / "ICBHI_final_database" / "114_1b4_Al_mc_AKGC417L.wav"
    if gravacao.is_file():
        destino = _copiar_par(paciente.id, "audio", gravacao, gravacao.with_suffix(".txt"))
        _enviar_e_analisar(paciente, "audio", destino, instante_s=0.0)
    else:
        print("  ICBHI ausente — rode `make data`")

    internacao = _DATA / "bidmc" / "bidmc32n.hea"
    if internacao.is_file():
        destino = _copiar_par(
            paciente.id, "sinais_vitais", internacao, internacao.with_suffix(".dat")
        )
        _enviar_e_analisar(paciente, "sinais_vitais", destino, instante_s=300.0)
    else:
        print("  BIDMC (bidmc32n) ausente — rode `make data`")


def main() -> int:
    print("Carga de pacientes de demonstração\n")
    _paciente_queda_e_ctg()
    _paciente_cirurgia_e_prescricao()
    _paciente_respiracao_e_internacao()
    print(
        "\nConcluído. Suba a API (`make serve-api`) e o painel (`make serve-front`) para explorar."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
