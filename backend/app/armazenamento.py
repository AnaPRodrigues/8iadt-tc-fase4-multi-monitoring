"""Armazenamento local dos arquivos enviados.

Os arquivos ficam em `data/uploads/<paciente>/<modalidade>/`; o banco guarda só o
caminho. A raiz é sobrescrevível por `APP_UPLOADS_DIR` (usado nos testes).
"""

import os
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_UPLOADS_DIR = _REPO_ROOT / "data" / "uploads"

_INSEGURO = re.compile(r"[^A-Za-z0-9._-]")


def uploads_dir() -> Path:
    env = os.environ.get("APP_UPLOADS_DIR")
    return Path(env) if env else _DEFAULT_UPLOADS_DIR


def _nome_seguro(nome: str) -> str:
    """Neutraliza separadores de caminho e caracteres estranhos do nome original."""
    return _INSEGURO.sub("_", Path(nome).name) or "arquivo"


def salvar_arquivo(paciente_id: str, modalidade: str, nome_original: str, conteudo: bytes) -> Path:
    """Grava o conteúdo em `data/uploads/<paciente>/<modalidade>/<nome>` e devolve
    o caminho. Prefixa o nome com um contador se já existir, para não sobrescrever."""
    destino_dir = uploads_dir() / paciente_id / modalidade
    destino_dir.mkdir(parents=True, exist_ok=True)

    nome = _nome_seguro(nome_original)
    destino = destino_dir / nome
    contador = 1
    while destino.exists():
        destino = destino_dir / f"{Path(nome).stem}-{contador}{Path(nome).suffix}"
        contador += 1

    destino.write_bytes(conteudo)
    return destino


def copiar_arquivo(paciente_id: str, modalidade: str, origem: Path) -> Path:
    """Copia um arquivo já existente no disco (ex.: um registro de dataset) para a
    área de uploads do paciente. Usado pela carga inicial de demonstração."""
    origem = Path(origem)
    return salvar_arquivo(paciente_id, modalidade, origem.name, origem.read_bytes())
