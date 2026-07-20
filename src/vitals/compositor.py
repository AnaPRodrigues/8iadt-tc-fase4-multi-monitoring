"""Compositor da timeline de demonstração (VITALS-07, AD-021).

Isto **não** é um gerador sintético: nenhum valor é inventado. A composição apenas
concatena registros reais na ordem declarada, para contar a história de deterioração
ao longo da internação. O dado permanece 100% real — só a ordenação é montada, e a
proveniência de cada trecho fica registrada para que toda evidência possa apontar o
registro de origem.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.logging import get_logger
from vitals.loader import Segment, VitalRecord, load_record

log = get_logger("vitals.compositor")


@dataclass(frozen=True)
class TimelineSpec:
    dataset_dir: Path
    record_ids: list[str]
    timeline_id: str = "timeline-demo"


def _resample(sinal: np.ndarray, fs_origem: float, fs_destino: float) -> np.ndarray:
    """Reamostra por interpolação linear para a taxa de destino."""
    if fs_origem == fs_destino or sinal.size == 0:
        return sinal
    duracao = len(sinal) / fs_origem
    n_destino = int(duracao * fs_destino)
    origem = np.arange(len(sinal)) / fs_origem
    destino = np.arange(n_destino) / fs_destino
    return np.interp(destino, origem, sinal)


def compose(spec: TimelineSpec) -> VitalRecord:
    """Concatena os registros declarados em uma timeline contínua.

    A taxa de amostragem de destino é a do primeiro registro. No CTU-UHB todos são
    4 Hz (fato verificado), então o resample é defensivo e normalmente não roda —
    mas sem ele registros com taxas diferentes produziriam uma timeline cujos
    timestamps não correspondem ao tempo real.

    O pH da timeline é o **mínimo** entre os registros: a narrativa é de deterioração,
    e o rótulo precisa refletir o pior desfecho alcançado.
    """
    if not spec.record_ids:
        raise ValueError("a timeline precisa declarar ao menos um registro")

    registros: list[VitalRecord] = []
    for record_id in spec.record_ids:
        caminho = Path(spec.dataset_dir) / record_id
        if not caminho.with_suffix(".hea").is_file():
            raise FileNotFoundError(f"registro inexistente na timeline: {record_id}")
        registros.append(load_record(caminho))

    fs_destino = registros[0].fs
    divergentes = [r.record_id for r in registros if r.fs != fs_destino]
    if divergentes:
        log.warning(
            "taxas divergentes normalizadas para %.1f Hz: %s", fs_destino, ", ".join(divergentes)
        )

    fhr_partes: list[np.ndarray] = []
    uc_partes: list[np.ndarray] = []
    proveniencia: list[Segment] = []
    cursor = 0

    for r in registros:
        fhr = _resample(r.fhr, r.fs, fs_destino)
        uc = _resample(r.uc, r.fs, fs_destino)
        fhr_partes.append(fhr)
        uc_partes.append(uc)
        proveniencia.append(
            Segment(source_record_id=r.record_id, start_idx=cursor, end_idx=cursor + len(fhr))
        )
        cursor += len(fhr)

    return VitalRecord(
        record_id=spec.timeline_id,
        fhr=np.concatenate(fhr_partes),
        uc=np.concatenate(uc_partes),
        fs=fs_destino,
        ph=min(r.ph for r in registros),
        provenance=proveniencia,
    )
