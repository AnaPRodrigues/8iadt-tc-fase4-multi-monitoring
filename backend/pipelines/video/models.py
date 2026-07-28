"""Dataclasses compartilhadas pelas duas raias do pipeline de vídeo (pose e objeto).

Um único módulo para os dois lados evita duplicar tipos que atravessam o
relatório consolidado (``report.py``).
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
    track_id: int | None = None  # ID persistente de tracking multi-pessoa (ByteTrack/IoU)


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


@dataclass(frozen=True)
class BoundingBox:
    class_name: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class AnnotatedFrame:
    image_path: Path
    boxes: list[BoundingBox]


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, width, height (formato COCO)


@dataclass(frozen=True)
class JointTarget:
    """Meta de amplitude articular para fisioterapia.

    Os índices ``landmark_a``, ``landmark_b``, ``landmark_c`` referem-se aos
    33 landmarks do MediaPipe Pose — ``b`` é o vértice do ângulo (ex.: joelho).
    """
    joint_name: str       # "knee_left", "knee_right", "elbow_left", "elbow_right"
    landmark_a: int       # proximal (ex.: 23 = hip para joelho)
    landmark_b: int       # vértice da articulação (ex.: 25 = knee)
    landmark_c: int       # distal (ex.: 27 = ankle para joelho)
    min_angle: float      # ângulo mínimo aceitável (graus)
    target_angle: float   # ângulo-alvo do exercício (graus)


@dataclass(frozen=True)
class PosturalFinding:
    """Achado de análise postural — desvio articular, inclinação de tronco ou queda."""
    finding_type: str      # "POSTURAL_DEVIATION" | "TRUNK_TILT" | "FALL_DETECTED"
    joint_name: str | None  # None para TRUNK_TILT e FALL_DETECTED
    measured_angle: float   # ângulo medido (graus)
    expected_angle: float   # ângulo esperado (graus)
    duration_s: float       # duração do evento (segundos)
    frame_index: int        # frame representativo
    score: float            # 0–1, normalizado
    description: str        # resumo em linguagem clínica
    track_id: int | None = None  # ID da pessoa que disparou o evento (para evidência)
    peak_frame: int | None = None  # frame exato do pico de Vy (para evidência)
