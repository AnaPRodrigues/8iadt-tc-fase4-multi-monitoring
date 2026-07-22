"""Testes da evidência de ciclo anômalo (AUDIO-05)."""

import json
from pathlib import Path

import numpy as np
import soundfile as sf

from pipelines.audio.icbhi_evidence import evidence_id_for, plot_spectrogram, save_cycle_evidence
from pipelines.audio.models import Prediction, RespiratoryCycle

SR = 4000


def _wav(path: Path, seconds: float = 1.0) -> None:
    t = np.linspace(0, seconds, int(seconds * SR), endpoint=False)
    sf.write(str(path), 0.5 * np.sin(2 * np.pi * 300 * t), SR)


def _ciclo(tmp_path: Path, label: str = "crackle") -> RespiratoryCycle:
    wav = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    _wav(wav)
    return RespiratoryCycle(
        record_id="101_1b1_Al_sc_Meditron",
        patient_id="101",
        cycle_index=3,
        start_s=0.0,
        end_s=1.0,
        wav_path=wav,
        label=label,
    )


def test_plot_spectrogram_gera_png_valido(tmp_path):
    cycle = _ciclo(tmp_path)
    destino = tmp_path / "out" / "spec.png"

    caminho = plot_spectrogram(cycle, destino)

    assert caminho.is_file()
    assert caminho.stat().st_size > 0


def test_evidence_id_for_e_deterministico(tmp_path):
    cycle = _ciclo(tmp_path)

    a = evidence_id_for(cycle, "crackle")
    b = evidence_id_for(cycle, "crackle")

    assert a == b
    assert cycle.record_id in a
    assert "crackle" in a
    assert str(cycle.cycle_index) in a


def test_ciclo_previsto_normal_nao_gera_evidencia(tmp_path):
    cycle = _ciclo(tmp_path, label="normal")
    pred = Prediction(
        record_id=cycle.record_id, cycle_index=cycle.cycle_index,
        predicted_label="normal", confidence=0.9,
    )

    resultado = save_cycle_evidence(cycle, pred, run_id="r1", output_root=tmp_path / "output")

    assert resultado is None
    assert not (tmp_path / "output").exists()


def test_ciclo_anomalo_gera_sidecar_com_metadados_esperados(tmp_path):
    cycle = _ciclo(tmp_path, label="wheeze")
    pred = Prediction(
        record_id=cycle.record_id, cycle_index=cycle.cycle_index,
        predicted_label="crackle", confidence=0.73,
    )

    evidencia = save_cycle_evidence(
        cycle, pred, run_id="r1", output_root=tmp_path / "output"
    )

    assert evidencia is not None
    assert evidencia.artifact_path.is_file()
    meta = json.loads(evidencia.sidecar_path.read_text(encoding="utf-8"))["metadata"]
    assert meta["record_id"] == cycle.record_id
    assert meta["cycle_index"] == cycle.cycle_index
    assert meta["predicted_label"] == "crackle"
    assert meta["real_label"] == "wheeze"
    assert meta["score"] == 0.73
