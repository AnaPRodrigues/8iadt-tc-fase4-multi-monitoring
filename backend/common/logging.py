"""Log estruturado compartilhado por todas as features."""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger("mm")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger sob o namespace do projeto, configurado uma única vez."""
    _configure()
    return logging.getLogger(f"mm.{name}")
