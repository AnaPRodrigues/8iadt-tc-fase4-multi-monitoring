"""Acesso ao banco local de pacientes — operações de leitura e escrita.

Cada função abre e fecha sua própria conexão (o banco é local e de baixo
volume). Identificadores são gerados aqui quando não informados.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.db import conectar

MODALIDADES = ("video", "audio", "documento", "sinais_vitais")
SITUACOES = ("recebido", "processando", "concluido", "erro")
NIVEIS = ("verde", "amarelo", "vermelho")


def _agora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _novo_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# Pacientes
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Paciente:
    id: str
    nome: str
    data_inicio: str
    observacoes: str | None


def criar_paciente(
    nome: str, data_inicio: str | None = None, observacoes: str | None = None
) -> Paciente:
    paciente = Paciente(
        id=_novo_id("p"),
        nome=nome,
        data_inicio=data_inicio or _agora(),
        observacoes=observacoes,
    )
    with conectar() as conn:
        conn.execute(
            "INSERT INTO pacientes (id, nome, data_inicio, observacoes) VALUES (?, ?, ?, ?)",
            (paciente.id, paciente.nome, paciente.data_inicio, paciente.observacoes),
        )
    return paciente


def listar_pacientes() -> list[Paciente]:
    with conectar() as conn:
        linhas = conn.execute("SELECT * FROM pacientes ORDER BY data_inicio").fetchall()
    return [_para_paciente(linha) for linha in linhas]


def obter_paciente(paciente_id: str) -> Paciente | None:
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
    return _para_paciente(linha) if linha else None


def remover_paciente(paciente_id: str) -> bool:
    """Remove o paciente e, em cascata, seus uploads/análises/alertas. Devolve
    `False` se o paciente não existia."""
    with conectar() as conn:
        cur = conn.execute("DELETE FROM pacientes WHERE id = ?", (paciente_id,))
    return cur.rowcount > 0


def _para_paciente(linha) -> Paciente:
    return Paciente(
        id=linha["id"],
        nome=linha["nome"],
        data_inicio=linha["data_inicio"],
        observacoes=linha["observacoes"],
    )


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Upload:
    id: str
    paciente_id: str
    modalidade: str
    caminho: str
    nome_original: str
    criado_em: str
    situacao: str


def criar_upload(paciente_id: str, modalidade: str, caminho: str, nome_original: str) -> Upload:
    upload = Upload(
        id=_novo_id("u"),
        paciente_id=paciente_id,
        modalidade=modalidade,
        caminho=caminho,
        nome_original=nome_original,
        criado_em=_agora(),
        situacao="recebido",
    )
    with conectar() as conn:
        conn.execute(
            "INSERT INTO uploads "
            "(id, paciente_id, modalidade, caminho, nome_original, criado_em, situacao) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                upload.id,
                upload.paciente_id,
                upload.modalidade,
                upload.caminho,
                upload.nome_original,
                upload.criado_em,
                upload.situacao,
            ),
        )
    return upload


def listar_uploads(paciente_id: str) -> list[Upload]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM uploads WHERE paciente_id = ? ORDER BY criado_em", (paciente_id,)
        ).fetchall()
    return [_para_upload(linha) for linha in linhas]


def obter_upload(upload_id: str) -> Upload | None:
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    return _para_upload(linha) if linha else None


def atualizar_situacao_upload(upload_id: str, situacao: str) -> None:
    with conectar() as conn:
        conn.execute("UPDATE uploads SET situacao = ? WHERE id = ?", (situacao, upload_id))


def _para_upload(linha) -> Upload:
    return Upload(
        id=linha["id"],
        paciente_id=linha["paciente_id"],
        modalidade=linha["modalidade"],
        caminho=linha["caminho"],
        nome_original=linha["nome_original"],
        criado_em=linha["criado_em"],
        situacao=linha["situacao"],
    )


# --------------------------------------------------------------------------- #
# Análises
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Analise:
    id: str
    upload_id: str
    modalidade: str
    resultado: dict
    pontuacao: float | None
    criado_em: str


def criar_analise(
    upload_id: str, modalidade: str, resultado: dict, pontuacao: float | None
) -> Analise:
    analise = Analise(
        id=_novo_id("a"),
        upload_id=upload_id,
        modalidade=modalidade,
        resultado=resultado,
        pontuacao=pontuacao,
        criado_em=_agora(),
    )
    with conectar() as conn:
        conn.execute(
            "INSERT INTO analises (id, upload_id, modalidade, resultado, pontuacao, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                analise.id,
                analise.upload_id,
                analise.modalidade,
                json.dumps(analise.resultado, ensure_ascii=False),
                analise.pontuacao,
                analise.criado_em,
            ),
        )
    return analise


def obter_analise_de_upload(upload_id: str) -> Analise | None:
    with conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM analises WHERE upload_id = ? ORDER BY criado_em DESC LIMIT 1",
            (upload_id,),
        ).fetchone()
    return _para_analise(linha) if linha else None


def listar_analises_do_paciente(paciente_id: str) -> list[Analise]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT a.* FROM analises a JOIN uploads u ON a.upload_id = u.id "
            "WHERE u.paciente_id = ? ORDER BY a.criado_em",
            (paciente_id,),
        ).fetchall()
    return [_para_analise(linha) for linha in linhas]


def _para_analise(linha) -> Analise:
    return Analise(
        id=linha["id"],
        upload_id=linha["upload_id"],
        modalidade=linha["modalidade"],
        resultado=json.loads(linha["resultado"]),
        pontuacao=linha["pontuacao"],
        criado_em=linha["criado_em"],
    )


# --------------------------------------------------------------------------- #
# Alertas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Alerta:
    id: str
    paciente_id: str
    nivel: str
    pontuacao: float
    criado_em: str
    motivo: str
    referencias: list[str]


def registrar_alerta(
    paciente_id: str, nivel: str, pontuacao: float, motivo: str, referencias: list[str]
) -> Alerta:
    alerta = Alerta(
        id=_novo_id("al"),
        paciente_id=paciente_id,
        nivel=nivel,
        pontuacao=pontuacao,
        criado_em=_agora(),
        motivo=motivo,
        referencias=referencias,
    )
    with conectar() as conn:
        conn.execute(
            "INSERT INTO alertas "
            "(id, paciente_id, nivel, pontuacao, criado_em, motivo, referencias) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                alerta.id,
                alerta.paciente_id,
                alerta.nivel,
                alerta.pontuacao,
                alerta.criado_em,
                alerta.motivo,
                json.dumps(alerta.referencias, ensure_ascii=False),
            ),
        )
    return alerta


def listar_alertas_do_paciente(paciente_id: str) -> list[Alerta]:
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM alertas WHERE paciente_id = ? ORDER BY criado_em DESC", (paciente_id,)
        ).fetchall()
    return [_para_alerta(linha) for linha in linhas]


def listar_todos_os_alertas() -> list[Alerta]:
    with conectar() as conn:
        linhas = conn.execute("SELECT * FROM alertas ORDER BY criado_em DESC").fetchall()
    return [_para_alerta(linha) for linha in linhas]


def _para_alerta(linha) -> Alerta:
    return Alerta(
        id=linha["id"],
        paciente_id=linha["paciente_id"],
        nivel=linha["nivel"],
        pontuacao=linha["pontuacao"],
        criado_em=linha["criado_em"],
        motivo=linha["motivo"],
        referencias=json.loads(linha["referencias"]),
    )
