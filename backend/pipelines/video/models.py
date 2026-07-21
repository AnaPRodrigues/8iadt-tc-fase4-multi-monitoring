"""Dataclasses compartilhadas pelas duas raias de F1 (pose e objeto).

Um único módulo para os dois lados evita duplicar tipos que atravessam o
relatório consolidado (``report.py``, T13).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sequence:
    seq_id: str
    label: str  # "fall" | "adl" -- derivado do nome do diretório
    frame_paths: list[Path]


@dataclass(frozen=True)
class PoseFrame:
    landmarks: list[tuple[float, float, float, float]]  # x, y, z, visibility (33 pontos)


@dataclass(frozen=True)
class MovementWindow:
    start_frame: int
    end_frame: int
    center_of_mass_amplitude: float
    velocity: float
    asymmetry: float


@dataclass(frozen=True)
class SequenceVerdict:
    seq_id: str
    predicted: str  # "queda" | "adl" | "dados_insuficientes"
    label: str  # "fall" | "adl" (rótulo real)
