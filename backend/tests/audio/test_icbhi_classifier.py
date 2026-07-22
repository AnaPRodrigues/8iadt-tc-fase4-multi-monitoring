"""Testes do classificador respiratório (AUDIO-02, AUDIO-03, AUDIO-14)."""

from pathlib import Path

import numpy as np
import soundfile as sf

from pipelines.audio.icbhi_classifier import predict, split_by_patient, train
from pipelines.audio.models import RespiratoryCycle

SR = 4000


def _wav_tom(path: Path, seconds: float, freq: float, ruido: float = 0.0) -> None:
    rng = np.random.default_rng(0)
    t = np.linspace(0, seconds, int(seconds * SR), endpoint=False)
    y = 0.6 * np.sin(2 * np.pi * freq * t)
    if ruido:
        y = y + ruido * rng.normal(size=y.shape)
    sf.write(str(path), y, SR)


def _ciclo(wav_path: Path, patient_id: str, cycle_index: int, label: str) -> RespiratoryCycle:
    return RespiratoryCycle(
        record_id=wav_path.stem,
        patient_id=patient_id,
        cycle_index=cycle_index,
        start_s=0.0,
        end_s=1.0,
        wav_path=wav_path,
        label=label,
    )


def _ciclo_sintetico(tmp_path: Path, patient_id: str, idx: int, label: str) -> RespiratoryCycle:
    """Ciclo com sinal separável por classe: tom grave (normal) vs. tom agudo+ruído (crackle)."""
    freq = 150.0 if label == "normal" else 2200.0
    ruido = 0.0 if label == "normal" else 0.15
    wav = tmp_path / f"{patient_id}_{idx}b1_Al_sc_Meditron.wav"
    _wav_tom(wav, seconds=1.0, freq=freq, ruido=ruido)
    return _ciclo(wav, patient_id, idx, label)


def _wav_tom_com_jitter(path: Path, seconds: float, freq: float, ruido: float,
                         rng: np.random.Generator) -> None:
    """Como ``_wav_tom``, mas com ``rng`` externo — permite jitter de freq/ruído por amostra,
    necessário para produzir classes com sobreposição parcial (não perfeitamente separáveis)."""
    t = np.linspace(0, seconds, int(seconds * SR), endpoint=False)
    y = 0.6 * np.sin(2 * np.pi * freq * t)
    y = y + ruido * rng.normal(size=y.shape)
    sf.write(str(path), y, SR)


def test_split_by_patient_nunca_mistura_o_mesmo_paciente_nos_dois_lados(tmp_path):
    cycles = []
    for p in range(10):
        pid = f"pat{p}"
        for c in range(3):
            cycles.append(_ciclo(tmp_path / f"{pid}_{c}.wav", pid, c, "normal"))

    treino, teste = split_by_patient(cycles, test_size=0.3, seed=42)

    pacientes_treino = {c.patient_id for c in treino}
    pacientes_teste = {c.patient_id for c in teste}

    assert not (pacientes_treino & pacientes_teste)
    assert len(treino) + len(teste) == len(cycles)


def test_train_e_predict_com_seed_fixo_e_deterministico(tmp_path):
    cycles = [
        _ciclo_sintetico(tmp_path, f"pat{i}", i, "normal" if i % 2 == 0 else "crackle")
        for i in range(10)
    ]
    alvo = _ciclo_sintetico(tmp_path, "pat_alvo", 99, "normal")

    modelo_a = train(cycles, seed=42)
    pred_a = predict(modelo_a, alvo)

    modelo_b = train(cycles, seed=42)
    pred_b = predict(modelo_b, alvo)

    assert pred_a.predicted_label == pred_b.predicted_label
    assert pred_a.confidence == pred_b.confidence


def test_predict_retorna_confianca_no_intervalo_0_1(tmp_path):
    cycles = [
        _ciclo_sintetico(tmp_path, f"pat{i}", i, "normal" if i % 2 == 0 else "crackle")
        for i in range(10)
    ]
    alvo = _ciclo_sintetico(tmp_path, "pat_alvo", 99, "crackle")

    modelo = train(cycles, seed=42)
    pred = predict(modelo, alvo)

    assert 0.0 <= pred.confidence <= 1.0


def test_classificador_acerta_a_classe_majoritaria_em_conjunto_separavel(tmp_path):
    """Prova que treino/predição estão conectados de fato, não apenas livres de exceção."""
    cycles = [
        _ciclo_sintetico(tmp_path, f"pat{i}", i, "normal" if i % 2 == 0 else "crackle")
        for i in range(20)
    ]
    modelo = train(cycles, seed=42)

    alvo_normal = _ciclo_sintetico(tmp_path, "pat_alvo_normal", 100, "normal")
    alvo_crackle = _ciclo_sintetico(tmp_path, "pat_alvo_crackle", 101, "crackle")

    assert predict(modelo, alvo_normal).predicted_label == "normal"
    assert predict(modelo, alvo_crackle).predicted_label == "crackle"


def test_class_weight_balanced_recupera_a_classe_minoritaria_em_conjunto_9_para_1(tmp_path):
    """Prova que `class_weight="balanced"` muda o comportamento do modelo (não só o parâmetro
    setado): num conjunto desbalanceado 9:1 (18 normal / 2 crackle) com classes parcialmente
    sobrepostas (frequências próximas + ruído), a classe minoritária só é predita corretamente
    com o balanceamento ligado (validation.md § Fix 2 — mutante sobrevivente)."""
    rng = np.random.default_rng(42)
    cycles = []
    for i in range(18):
        freq = 300.0 + rng.normal(scale=20)
        wav = tmp_path / f"patn{i}_1b1_Al_sc_Meditron.wav"
        _wav_tom_com_jitter(wav, seconds=1.0, freq=freq, ruido=0.45, rng=rng)
        cycles.append(_ciclo(wav, f"patn{i}", i, "normal"))
    for i in range(2):
        freq = 380.0 + rng.normal(scale=20)
        wav = tmp_path / f"patc{i}_1b1_Al_sc_Meditron.wav"
        _wav_tom_com_jitter(wav, seconds=1.0, freq=freq, ruido=0.45, rng=rng)
        cycles.append(_ciclo(wav, f"patc{i}", i, "crackle"))

    alvo_wav = tmp_path / "pat_alvo_1b1_Al_sc_Meditron.wav"
    _wav_tom_com_jitter(
        alvo_wav, seconds=1.0, freq=380.0, ruido=0.45, rng=np.random.default_rng(43)
    )
    alvo = _ciclo(alvo_wav, "pat_alvo", 99, "crackle")

    modelo = train(cycles, seed=42)
    pred = predict(modelo, alvo)

    assert pred.predicted_label == "crackle"
