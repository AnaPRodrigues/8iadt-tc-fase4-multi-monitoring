"""Carga de uma sequência do URFD (VIDEO-01, carga).

Layout real (verificado em F0/Design): ``<seq>/<seq>-cam0-rgb/<seq>-cam0-rgb-NNN.png``.
O rótulo é o nome do diretório da sequência (``fall-NN``/``adl-NN``) -- URFD não
fornece anotação por frame do instante da queda (ver Out of Scope da spec).
"""

import re
from pathlib import Path

from common.logging import get_logger
from pipelines.video.models import Sequence

log = get_logger("video.pose_loader")

_FRAME_NUMBER_RE = re.compile(r"(\d+)$")


def _frame_number(path: Path) -> int:
    match = _FRAME_NUMBER_RE.search(path.stem)
    if not match:
        raise ValueError(f"nome de frame sem número reconhecível: {path.name!r}")
    return int(match.group(1))


def load_sequence(seq_dir: Path) -> Sequence:
    """Lê os PNGs em ordem numérica (não alfabética) e deriva o rótulo do diretório.

    Um diretório fora do padrão ``fall-NN``/``adl-NN`` nunca vira um rótulo
    adivinhado -- levanta ``ValueError`` explícito.
    """
    seq_dir = Path(seq_dir)
    seq_id = seq_dir.name

    if seq_id.startswith("fall-"):
        label = "fall"
    elif seq_id.startswith("adl-"):
        label = "adl"
    else:
        raise ValueError(
            f"diretório de sequência desconhecido: {seq_id!r} (esperado 'fall-NN' ou 'adl-NN')"
        )

    frames_dir = seq_dir / f"{seq_id}-cam0-rgb"
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"diretório de frames RGB ausente: {frames_dir}")

    frame_paths = sorted(frames_dir.glob("*.png"), key=_frame_number)
    if not frame_paths:
        log.warning("sequência %s sem frames PNG em %s", seq_id, frames_dir)

    return Sequence(seq_id=seq_id, label=label, frame_paths=frame_paths)
