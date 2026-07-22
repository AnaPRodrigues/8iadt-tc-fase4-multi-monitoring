"""Testes de transcrição local (AUDIO-06, AUDIO-10, AUDIO-14)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from pipelines.audio.transcribe import transcribe

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ICBHI_DIR = _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"


@dataclass
class _FakeSegment:
    start: float
    end: float
    text: str
    no_speech_prob: float


class _FakeInfo:
    language = "pt"


class _FakeModel:
    """Substitui ``WhisperModel`` real: segmentos controlados + kwargs recebidos registrados."""

    def __init__(self, segments):
        self._segments = segments
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append({"audio": audio, **kwargs})
        return iter(self._segments), _FakeInfo()


def test_reliable_true_quando_texto_nao_vazio_e_no_speech_prob_baixo(tmp_path):
    fake = _FakeModel(
        [
            _FakeSegment(0.0, 1.0, " Bom dia, doutor.", no_speech_prob=0.1),
            _FakeSegment(1.0, 2.0, " Como o senhor está?", no_speech_prob=0.05),
        ]
    )

    transcript = transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert transcript.reliable is True
    assert transcript.text.strip() != ""


def test_reliable_false_quando_no_speech_prob_medio_acima_do_limiar(tmp_path):
    fake = _FakeModel(
        [
            _FakeSegment(0.0, 1.0, " ruido", no_speech_prob=0.9),
            _FakeSegment(1.0, 2.0, " ruido", no_speech_prob=0.95),
        ]
    )

    transcript = transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert transcript.reliable is False


def test_reliable_no_limiar_exato_e_true(tmp_path):
    """média de no_speech_prob == no_speech_threshold conta como confiável (<=, não <)."""
    fake = _FakeModel([_FakeSegment(0.0, 1.0, " texto", no_speech_prob=0.6)])

    transcript = transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert transcript.reliable is True


def test_reliable_false_quando_texto_vazio_mesmo_com_no_speech_prob_baixo(tmp_path):
    fake = _FakeModel([_FakeSegment(0.0, 1.0, "", no_speech_prob=0.0)])

    transcript = transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert transcript.reliable is False


def test_reliable_false_quando_nenhum_segmento_e_devolvido(tmp_path):
    fake = _FakeModel([])

    transcript = transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert transcript.reliable is False
    assert transcript.text == ""


def test_model_transcribe_e_chamado_com_temperature_zero(tmp_path):
    fake = _FakeModel([_FakeSegment(0.0, 1.0, " oi", no_speech_prob=0.1)])

    transcribe(tmp_path / "audio.wav", "tiny", no_speech_threshold=0.6, model=fake)

    assert len(fake.calls) == 1
    assert fake.calls[0]["temperature"] == 0.0


@pytest.mark.integration
def test_transcricao_de_audio_icbhi_real_sem_fala_produz_reliable_false():
    """Caso negativo real: som respiratório (sem fala) transcrito com o modelo 'tiny' real."""
    if not _ICBHI_DIR.is_dir():
        pytest.skip(f"dataset ICBHI ausente em {_ICBHI_DIR} — rode `make data`")

    wavs = sorted(_ICBHI_DIR.glob("*.wav"))
    assert wavs, f"nenhum wav encontrado em {_ICBHI_DIR}"

    transcript = transcribe(wavs[0], model_size="tiny", no_speech_threshold=0.6)

    assert transcript.reliable is False
