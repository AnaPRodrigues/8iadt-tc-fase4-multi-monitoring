"""Transcrição local pt-BR via faster-whisper, com flag de confiabilidade.

``temperature=0.0`` fixo desliga o fallback estocástico de temperaturas do
faster-whisper (o default é uma lista `[0.0, 0.2, ...]`), condição necessária
para o determinismo exigido (confirmado via introspecção real da
assinatura de ``WhisperModel.transcribe`` nesta sessão).
"""

from pathlib import Path
from typing import Any

from common.logging import get_logger
from pipelines.audio.models import Transcript, TranscriptSegment

log = get_logger("audio.transcribe")


def transcribe(
    audio_path: Path,
    model_size: str,
    no_speech_threshold: float,
    model: Any = None,
) -> Transcript:
    """Transcreve ``audio_path`` em pt-BR.

    ``model`` é injetável (fake nos testes unit) para não pagar o custo de uma
    inferência real a cada teste; sem injeção, constrói um ``WhisperModel`` CPU real.

    ``Transcript.text`` é a concatenação bruta (sem strip) dos textos de
    segmento, para que os offsets de caractere batam com os limites de
    segmento — usado por ``critical_terms.find_terms`` para o timestamp
    aproximado do match.
    """
    audio_path = Path(audio_path)

    if model is None:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments_iter, _info = model.transcribe(
        str(audio_path), language="pt", temperature=0.0, beam_size=5
    )

    segments = [
        TranscriptSegment(
            start_s=seg.start,
            end_s=seg.end,
            text=seg.text,
            no_speech_prob=seg.no_speech_prob,
        )
        for seg in segments_iter
    ]

    text = "".join(seg.text for seg in segments)

    # sem segmentos: nada a considerar confiável
    avg_no_speech = (
        sum(seg.no_speech_prob for seg in segments) / len(segments) if segments else 1.0
    )

    reliable = bool(text.strip()) and avg_no_speech <= no_speech_threshold

    return Transcript(audio_path=audio_path, text=text, segments=segments, reliable=reliable)
