"""Leitura de registros CTU-UHB e rotulagem de ground truth.

O rótulo de anomalia é clínico e real — o pH do cordão umbilical registrado no
próprio header — e não uma anomalia injetada.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb

from common.logging import get_logger

log = get_logger("vitals.loader")

# pH < 7.05 ≈ acidose/sofrimento fetal. Limiar adotado da literatura clínica, não
# calibrado por este projeto (ver Out of Scope da spec).
PH_THRESHOLD = 7.05

_FHR = "FHR"
_UC = "UC"

# O wfdb entrega comentários já sem o '#' inicial (verificado em REPL, wfdb 4.3.1):
# a linha `#pH           7.26` do .hea chega como `'pH           7.26'`.
# A âncora de início evita casar `pCO2` ou `pH_alt`.
_PH_RE = re.compile(r"^pH\s+(\S+)\s*$")


def parse_ph(comments: list[str]) -> float | None:
    """Extrai o pH do cordão das linhas de comentário do header.

    Retorna ``None`` quando o campo está ausente ou não é numérico — o registro é
    então descartado do lote pelo chamador, nunca rotulado por suposição.
    """
    for line in comments:
        match = _PH_RE.match(line.strip())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def is_pathological(ph: float) -> bool:
    """Rótulo de ground truth: ``True`` quando o pH indica acidose."""
    return ph < PH_THRESHOLD


class InvalidRecordError(Exception):
    """Registro inutilizável — sinal ou rótulo ausente/ilegível."""


@dataclass(frozen=True)
class Segment:
    """Trecho de uma série e o registro real de onde veio."""

    source_record_id: str
    start_idx: int
    end_idx: int


@dataclass(frozen=True)
class VitalRecord:
    record_id: str
    fhr: np.ndarray
    uc: np.ndarray
    fs: float
    ph: float
    provenance: list[Segment]


@dataclass(frozen=True)
class LoadFailure:
    record_id: str
    reason: str


def _canal(record, nome: str) -> np.ndarray:
    if not record.sig_name or nome not in record.sig_name:
        raise InvalidRecordError(f"canal {nome} ausente no registro {record.record_name}")
    return np.asarray(record.p_signal[:, record.sig_name.index(nome)], dtype=float)


def load_record(record_path: Path) -> VitalRecord:
    """Lê um registro CTU-UHB (sinais + pH). Levanta ``InvalidRecordError`` se inutilizável."""
    try:
        record = wfdb.rdrecord(str(record_path))
    except Exception as exc:  # wfdb levanta tipos variados para header/dados inválidos
        raise InvalidRecordError(f"falha ao ler {record_path}: {exc}") from exc

    fhr = _canal(record, _FHR)
    uc = _canal(record, _UC)

    ph = parse_ph(record.comments or [])
    if ph is None:
        raise InvalidRecordError(f"pH ausente ou ilegível em {record_path}")

    record_id = record.record_name or Path(record_path).name
    return VitalRecord(
        record_id=record_id,
        fhr=fhr,
        uc=uc,
        fs=float(record.fs),
        ph=ph,
        provenance=[Segment(source_record_id=record_id, start_idx=0, end_idx=len(fhr))],
    )


def load_dataset(directory: Path) -> tuple[list[VitalRecord], list[LoadFailure]]:
    """Lê todos os registros do diretório, descartando os inválidos sem parar o lote.

    Um registro corrompido no meio do dataset não pode custar a execução inteira
    — a contagem de descartes vai para o log e o chamador decide o que fazer.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"diretório de dataset inexistente: {directory}")

    registros: list[VitalRecord] = []
    falhas: list[LoadFailure] = []

    for header in sorted(directory.glob("*.hea")):
        base = header.with_suffix("")
        try:
            registros.append(load_record(base))
        except InvalidRecordError as exc:
            falhas.append(LoadFailure(record_id=base.name, reason=str(exc)))

    if falhas:
        log.warning(
            "%d registro(s) descartado(s) de %d: %s",
            len(falhas),
            len(falhas) + len(registros),
            ", ".join(f.record_id for f in falhas),
        )

    return registros, falhas
