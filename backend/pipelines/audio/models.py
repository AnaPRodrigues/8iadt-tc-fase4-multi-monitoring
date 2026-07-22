"""Dataclasses compartilhadas por todas as raias de F2 (P1/P2/P3).

Um único módulo para as três raias evita duplicar tipos que atravessam a
orquestração (``cli.py``), mesmo precedente de ``pipelines/video/models.py`` (F1/T1).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IcbhiRecordingMeta:
    patient_id: str
    recording_index: str
    chest_location: str
    acquisition_mode: str
    equipment: str


@dataclass(frozen=True)
class RespiratoryCycle:
    record_id: str  # nome do arquivo sem extensão
    patient_id: str
    cycle_index: int
    start_s: float
    end_s: float
    wav_path: Path
    label: str  # "normal" | "crackle" | "wheeze" | "both"


@dataclass(frozen=True)
class Prediction:
    record_id: str
    cycle_index: int
    predicted_label: str
    confidence: float


@dataclass(frozen=True)
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str
    no_speech_prob: float


@dataclass(frozen=True)
class Transcript:
    audio_path: Path
    text: str
    segments: list[TranscriptSegment]
    reliable: bool


@dataclass(frozen=True)
class CriticalTermHit:
    term: str
    context: str
    approx_timestamp_s: float | None


@dataclass(frozen=True)
class SentimentResult:
    label: str  # "positivo" | "negativo" | "neutro"
    score: float


@dataclass(frozen=True)
class AcousticFeatures:
    jitter_local: float
    shimmer_local: float
    hnr_db: float
    pause_rate: float
    speaking_rate_wps: float
