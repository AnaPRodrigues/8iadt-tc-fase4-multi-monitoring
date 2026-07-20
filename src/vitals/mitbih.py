"""Adaptador opcional para o MIT-BIH Arrhythmia (VITALS-11, P3).

Segundo caso de série vital com rótulo real: aqui o ground truth vem das anotações
de batimento feitas por especialistas, não do pH. O dataset é explicitamente
opcional — ``mitbih_disponivel`` permite ao pipeline pular este caso sem
interromper a execução do CTU-UHB.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

from core.logging import get_logger

log = get_logger("vitals.mitbih")

# Extensão do arquivo de anotação de batimentos do MIT-BIH.
MITBIH_ANNOTATOR = "atr"

# Na convenção do MIT-BIH, 'N' marca batimento normal; os demais símbolos de
# batimento indicam alguma arritmia.
NORMAL_SYMBOL = "N"


@dataclass(frozen=True)
class MITBIHRecord:
    record_id: str
    ecg: np.ndarray
    fs: float
    annotations: list[str]
    anomalous_beats: int

    @property
    def has_anomaly(self) -> bool:
        return self.anomalous_beats > 0


def mitbih_disponivel(directory: Path) -> bool:
    """Diz se há registros MIT-BIH utilizáveis no diretório."""
    directory = Path(directory)
    if not directory.is_dir():
        return False
    return any(directory.glob("*.atr"))


def load_mitbih_record(record_path: Path) -> MITBIHRecord:
    """Lê um registro MIT-BIH com suas anotações de batimento."""
    record_path = Path(record_path)
    if not record_path.with_suffix(f".{MITBIH_ANNOTATOR}").is_file():
        raise FileNotFoundError(f"anotações ausentes para o registro {record_path}")

    record = wfdb.rdrecord(str(record_path))
    ann = wfdb.rdann(str(record_path), MITBIH_ANNOTATOR)

    simbolos = list(ann.symbol)
    return MITBIHRecord(
        record_id=record.record_name or record_path.name,
        ecg=np.asarray(record.p_signal[:, 0], dtype=float),
        fs=float(record.fs),
        annotations=simbolos,
        anomalous_beats=sum(1 for s in simbolos if s != NORMAL_SYMBOL),
    )


def load_mitbih_dataset(directory: Path) -> list[MITBIHRecord]:
    """Lê todos os registros do diretório; devolve lista vazia se indisponível.

    Ausência do dataset não é erro: o caso de estudo é opcional e o pipeline
    principal (CTU-UHB) deve seguir normalmente (VITALS-11).
    """
    if not mitbih_disponivel(directory):
        log.info("MIT-BIH indisponível em %s — caso de estudo opcional pulado", directory)
        return []

    registros: list[MITBIHRecord] = []
    for atr in sorted(Path(directory).glob("*.atr")):
        try:
            registros.append(load_mitbih_record(atr.with_suffix("")))
        except Exception as exc:  # wfdb levanta tipos variados
            log.warning("registro MIT-BIH %s ignorado: %s", atr.stem, exc)
    return registros
