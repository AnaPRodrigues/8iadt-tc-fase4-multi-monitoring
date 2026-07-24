"""Registro de atividade do sistema, pensado para ser lido no terminal durante a
demonstração.

Cada linha traz o contexto entre colchetes e, quando a etapa envolve
processamento, a **origem**: `[LOCAL]` quando resolvida por modelo/biblioteca na
própria máquina, `[AWS]` quando houve chamada a um serviço gerenciado. As
mensagens incluem o paciente e a modalidade para dar contexto.

O horário é adicionado pelo formatador de log (ver `common/logging.py`).
"""

from common.logging import get_logger

log = get_logger("atividade")

_LABEL_MODALIDADE = {
    "video": "vídeo",
    "audio": "áudio",
    "sinais_vitais": "sinais vitais",
    "documento": "prescrição",
}


def rotulo_modalidade(modalidade: str) -> str:
    return _LABEL_MODALIDADE.get(modalidade, modalidade)


def _tamanho(bytes_: int) -> str:
    if bytes_ >= 1_000_000:
        return f"{bytes_ / 1_000_000:.1f} MB"
    if bytes_ >= 1_000:
        return f"{bytes_ / 1_000:.1f} KB"
    return f"{bytes_} B"


# --- Fronteiras do fluxo ---------------------------------------------------- #
def arquivo_recebido(paciente_id: str, modalidade: str, nome: str, tamanho_bytes: int) -> None:
    log.info(
        "[paciente:%s] arquivo recebido — modalidade=%s, %s (%s)",
        paciente_id,
        rotulo_modalidade(modalidade),
        nome,
        _tamanho(tamanho_bytes),
    )


def analise_iniciada(paciente_id: str, modalidade: str) -> None:
    log.info("[%s] análise iniciada — paciente %s", rotulo_modalidade(modalidade), paciente_id)


def analise_concluida(modalidade: str, duracao_s: float, resumo: str) -> None:
    log.info(
        "[%s] análise concluída em %.1fs — %s", rotulo_modalidade(modalidade), duracao_s, resumo
    )


def analise_falhou(modalidade: str, motivo: str) -> None:
    log.info("[%s] análise não pôde ser feita — %s", rotulo_modalidade(modalidade), motivo)


# --- Origem do processamento ------------------------------------------------ #
def local(modalidade: str, mensagem: str) -> None:
    """Etapa resolvida localmente (modelo/biblioteca na própria máquina)."""
    log.info("[%s][LOCAL] %s", rotulo_modalidade(modalidade), mensagem)


def nuvem_chamando(modalidade: str, servico: str, operacao: str, alvo: str) -> None:
    """Início de uma chamada a serviço gerenciado da AWS."""
    log.info("[%s][AWS] %s %s — %s", rotulo_modalidade(modalidade), servico, operacao, alvo)


def nuvem_concluida(
    modalidade: str, resumo: str, duracao_s: float, request_id: str
) -> None:
    """Fim de uma chamada de nuvem, com duração e o id da resposta — evidência de
    que a chamada foi real."""
    log.info(
        "[%s][AWS] %s em %.1fs — requestId=%s",
        rotulo_modalidade(modalidade),
        resumo,
        duracao_s,
        request_id,
    )


# --- Risco e alerta --------------------------------------------------------- #
def risco(pontuacao_anterior: float, pontuacao_nova: float, nivel: str) -> None:
    log.info(
        "[risco] pontuação %.2f -> %.2f — nível %s",
        pontuacao_anterior,
        pontuacao_nova,
        nivel.upper(),
    )


def alerta_registrado(paciente_id: str, motivo: str) -> None:
    log.info("[alerta] registrado para %s — motivo: %s", paciente_id, motivo)
