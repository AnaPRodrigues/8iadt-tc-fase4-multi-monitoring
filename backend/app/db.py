"""Banco local de pacientes (SQLite).

Guarda pacientes, arquivos enviados, resultados de análise e alertas. O arquivo
do banco fica em `data/app.db` por padrão (fora do controle de versão); os testes
apontam para um arquivo temporário pela variável de ambiente `APP_DB_PATH`.

O banco guarda apenas o *caminho* dos arquivos enviados, nunca o conteúdo — os
arquivos vivem em `data/uploads/<paciente>/<modalidade>/`.
"""

import os
import sqlite3
from pathlib import Path

from common.logging import get_logger

log = get_logger("app.db")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "app.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pacientes (
    id            TEXT PRIMARY KEY,
    nome          TEXT NOT NULL,
    data_inicio   TEXT NOT NULL,
    observacoes   TEXT
);

CREATE TABLE IF NOT EXISTS uploads (
    id             TEXT PRIMARY KEY,
    paciente_id    TEXT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    modalidade     TEXT NOT NULL,
    caminho        TEXT NOT NULL,
    nome_original  TEXT NOT NULL,
    criado_em      TEXT NOT NULL,
    situacao       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analises (
    id           TEXT PRIMARY KEY,
    upload_id    TEXT NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    modalidade   TEXT NOT NULL,
    resultado    TEXT NOT NULL,
    pontuacao    REAL,
    criado_em    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alertas (
    id           TEXT PRIMARY KEY,
    paciente_id  TEXT NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    nivel        TEXT NOT NULL,
    pontuacao    REAL NOT NULL,
    criado_em    TEXT NOT NULL,
    motivo       TEXT NOT NULL,
    referencias  TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Caminho do arquivo do banco (sobrescrevível por `APP_DB_PATH` nos testes)."""
    env = os.environ.get("APP_DB_PATH")
    return Path(env) if env else _DEFAULT_DB_PATH


def conectar() -> sqlite3.Connection:
    """Abre uma conexão, garante o esquema e liga as chaves estrangeiras.

    Idempotente: cria as tabelas se ainda não existem. Linhas vêm como
    `sqlite3.Row` (acesso por nome de coluna).
    """
    caminho = db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn
