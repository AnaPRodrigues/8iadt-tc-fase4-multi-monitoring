"""Gráfico de evidência da janela anômala.

Backend Agg fixado: a demo roda sem display (CI e notebook headless), e sem isso
o matplotlib tentaria abrir uma janela interativa e falharia.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from vitals.detectors import AnomalyEvent  # noqa: E402
from vitals.loader import VitalRecord  # noqa: E402


def titulo_evidencia(record: VitalRecord, event: AnomalyEvent) -> str:
    """Título que identifica registro, pH, detector e proveniência do trecho."""
    base = (
        f"{record.record_id} | pH {record.ph:.2f} | {event.detector} "
        f"| score {event.score:.2f} | {event.start_s:.1f}–{event.end_s:.1f}s"
    )
    if event.source_record_id != event.record_id:
        base += f" | origem: {event.source_record_id}"
    return base


def plot_anomaly_window(record: VitalRecord, event: AnomalyEvent, out_path: Path) -> Path:
    """Plota FHR e UC com a janela anômala destacada e grava em ``out_path``."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tempo = [i / record.fs for i in range(len(record.fhr))]

    fig, (ax_fhr, ax_uc) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    ax_fhr.plot(tempo, record.fhr, linewidth=0.8, color="#1f77b4")
    ax_fhr.set_ylabel("FHR (bpm)")
    ax_uc.plot(tempo, record.uc, linewidth=0.8, color="#2ca02c")
    ax_uc.set_ylabel("UC")
    ax_uc.set_xlabel("tempo (s)")

    for ax in (ax_fhr, ax_uc):
        ax.axvspan(event.start_s, event.end_s, color="#d62728", alpha=0.25)

    ax_fhr.set_title(titulo_evidencia(record, event))
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)

    return out_path
