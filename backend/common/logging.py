"""Log de atividade compartilhado por todas as partes do sistema.

O formato é pensado para ser lido no terminal durante a demonstração: horário,
o contexto entre colchetes (ex.: `[áudio][LOCAL]`) e a mensagem em português. O
contexto vem embutido na própria mensagem (ver `common/atividade.py`).
"""

import logging
import sys

# Só horário (não a data inteira) + mensagem -- linhas curtas e legíveis.
_FORMAT = "%(asctime)s %(message)s"
_DATEFMT = "%H:%M:%S"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    root = logging.getLogger("mm")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger sob o namespace do projeto, configurado uma única vez."""
    _configure()
    return logging.getLogger(f"mm.{name}")
