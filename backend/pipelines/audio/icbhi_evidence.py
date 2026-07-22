"""Evidência de ciclo anômalo: espectrograma + metadados (AUDIO-05).

Backend Agg fixado: a demo roda sem display (mesmo motivo de ``pipelines/vitals/plot.py``).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import librosa  # noqa: E402
import librosa.display  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common.evidence import Evidence, evidence_dir, save_evidence  # noqa: E402
from pipelines.audio.models import Prediction, RespiratoryCycle  # noqa: E402

_FEATURE = "audio"


def plot_spectrogram(cycle: RespiratoryCycle, path: Path, sr: int = 4000) -> Path:
    """Mel-spectrogram em dB do trecho ``[start_s, end_s]`` do ciclo, salvo como PNG."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    duracao = max(cycle.end_s - cycle.start_s, 0.0)
    y, _ = librosa.load(
        str(cycle.wav_path), sr=sr, offset=cycle.start_s, duration=duracao, mono=True
    )
    if y.size == 0:
        y = np.zeros(1, dtype=float)

    mel = librosa.feature.melspectrogram(y=y, sr=sr)
    mel_db = librosa.power_to_db(mel, ref=np.max)

    fig, ax = plt.subplots()
    librosa.display.specshow(mel_db, sr=sr, x_axis="time", y_axis="mel", ax=ax)
    ax.set_title(f"{cycle.record_id} ciclo {cycle.cycle_index}")
    fig.savefig(path, dpi=100)
    plt.close(fig)

    return path


def evidence_id_for(cycle: RespiratoryCycle, predicted: str) -> str:
    """Identificador determinístico da evidência, derivado do ciclo e da predição."""
    return f"{cycle.record_id}-cycle{cycle.cycle_index}-{predicted}"


def save_cycle_evidence(
    cycle: RespiratoryCycle,
    prediction: Prediction,
    run_id: str,
    output_root: str | Path = "output",
) -> Evidence | None:
    """Gera espectrograma + sidecar quando a classe prevista é anômala (≠ ``"normal"``).

    Ciclo previsto como ``"normal"`` não produz evidência alguma.
    """
    if prediction.predicted_label == "normal":
        return None

    evidence_id = evidence_id_for(cycle, prediction.predicted_label)
    dest_dir = evidence_dir(_FEATURE, run_id, output_root)
    artifact_path = plot_spectrogram(cycle, dest_dir / f"{evidence_id}.png")

    return save_evidence(
        feature=_FEATURE,
        run_id=run_id,
        evidence_id=evidence_id,
        source_record_id=cycle.record_id,
        artifact_path=artifact_path,
        metadata={
            "record_id": cycle.record_id,
            "cycle_index": cycle.cycle_index,
            "predicted_label": prediction.predicted_label,
            "real_label": cycle.label,
            "score": prediction.confidence,
        },
        root=output_root,
    )
