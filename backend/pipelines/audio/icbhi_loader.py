"""Leitura do ICBHI 2017: parsing de nome de arquivo, ciclos anotados e subconjunto curado.

O rótulo do ciclo é derivado das duas flags binárias (crackle, wheeze) da anotação
real do especialista: ``"both"`` é uma 4ª classe explícita, nunca descartada nem
colapsada em ``"crackle"`` por acidente — o rótulo real do ICBHI permite as duas anomalias
simultâneas, e dado real rotulado não é descartado por conveniência.
"""

import random
from pathlib import Path

import soundfile as sf

from common.logging import get_logger
from pipelines.audio.models import IcbhiRecordingMeta, RespiratoryCycle

log = get_logger("audio.icbhi_loader")

_N_FILENAME_FIELDS = 5
_N_ANNOTATION_COLUMNS = 4


def parse_filename(name: str) -> IcbhiRecordingMeta:
    """Extrai os 5 campos do formato documentado em ``filename_format.txt`` do ICBHI."""
    stem = Path(name).stem
    parts = stem.split("_")
    if len(parts) != _N_FILENAME_FIELDS:
        raise ValueError(f"nome de arquivo fora do formato ICBHI: {name!r}")

    patient_id, recording_index, chest_location, acquisition_mode, equipment = parts
    return IcbhiRecordingMeta(
        patient_id=patient_id,
        recording_index=recording_index,
        chest_location=chest_location,
        acquisition_mode=acquisition_mode,
        equipment=equipment,
    )


def _label(crackle: str, wheeze: str) -> str | None:
    """Rótulo do ciclo a partir das duas flags binárias, ou ``None`` se inválidas."""
    if crackle not in ("0", "1") or wheeze not in ("0", "1"):
        return None
    if crackle == "1" and wheeze == "1":
        return "both"
    if crackle == "1":
        return "crackle"
    if wheeze == "1":
        return "wheeze"
    return "normal"


def load_cycles(txt_path: Path, wav_path: Path) -> list[RespiratoryCycle]:
    """Lê os ciclos anotados de um par ``.txt``/``.wav``.

    Uma linha malformada (coluna faltando ou valor ilegível) é excluída do
    resultado, nunca contada como erro do classificador.
    """
    record_id = Path(wav_path).stem
    meta = parse_filename(Path(wav_path).name)

    cycles: list[RespiratoryCycle] = []
    for idx, line in enumerate(Path(txt_path).read_text(encoding="utf-8").splitlines()):
        fields = line.strip().split("\t")
        if len(fields) != _N_ANNOTATION_COLUMNS:
            continue
        start_raw, end_raw, crackle, wheeze = fields
        try:
            start_s = float(start_raw)
            end_s = float(end_raw)
        except ValueError:
            continue

        label = _label(crackle, wheeze)
        if label is None:
            continue

        cycles.append(
            RespiratoryCycle(
                record_id=record_id,
                patient_id=meta.patient_id,
                cycle_index=idx,
                start_s=start_s,
                end_s=end_s,
                wav_path=Path(wav_path),
                label=label,
            )
        )
    return cycles


def load_dataset(dataset_dir: Path) -> tuple[list[RespiratoryCycle], list[str]]:
    """Lê todos os pares ``.wav``/``.txt`` do diretório, sem parar o lote em falha.

    Arquivo sem anotação correspondente ou WAV corrompido/ilegível é pulado e
    reportado na lista de falhas.
    """
    dataset_dir = Path(dataset_dir)
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"diretório de dataset inexistente: {dataset_dir}")

    cycles: list[RespiratoryCycle] = []
    falhas: list[str] = []

    for wav_path in sorted(dataset_dir.glob("*.wav")):
        txt_path = wav_path.with_suffix(".txt")
        if not txt_path.is_file():
            falhas.append(wav_path.name)
            continue
        try:
            sf.info(str(wav_path))
        except Exception as exc:  # soundfile levanta tipos variados para WAV inválido
            log.warning("arquivo descartado (%s): %s", wav_path.name, exc)
            falhas.append(wav_path.name)
            continue

        cycles.extend(load_cycles(txt_path, wav_path))

    if falhas:
        log.warning("%d arquivo(s) descartado(s): %s", len(falhas), ", ".join(falhas))

    return cycles, falhas


def select_subset(
    cycles_by_patient: dict[str, list[RespiratoryCycle]], max_patients: int, seed: int
) -> list[RespiratoryCycle]:
    """Amostra determinística de pacientes (nunca de ciclos soltos).

    Preserva a integridade paciente→ciclos exigida pelo split sem vazamento em
    ``icbhi_classifier.py``.
    """
    pacientes = sorted(cycles_by_patient)
    escolhidos = random.Random(seed).sample(pacientes, min(max_patients, len(pacientes)))

    resultado: list[RespiratoryCycle] = []
    for pid in escolhidos:
        resultado.extend(cycles_by_patient[pid])
    return resultado
