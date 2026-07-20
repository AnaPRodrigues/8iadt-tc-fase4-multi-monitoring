"""Leitura de registros CTU-UHB e rotulagem de ground truth.

O rótulo de anomalia é clínico e real — o pH do cordão umbilical registrado no
próprio header — e não uma anomalia injetada (AD-015, AD-021).
"""

import re

# pH < 7.05 ≈ acidose/sofrimento fetal. Limiar adotado da literatura clínica, não
# calibrado por este projeto (ver Out of Scope da spec).
PH_THRESHOLD = 7.05

# O wfdb entrega comentários já sem o '#' inicial (verificado em REPL, wfdb 4.3.1):
# a linha `#pH           7.26` do .hea chega como `'pH           7.26'`.
# A âncora de início evita casar `pCO2` ou `pH_alt`.
_PH_RE = re.compile(r"^pH\s+(\S+)\s*$")


def parse_ph(comments: list[str]) -> float | None:
    """Extrai o pH do cordão das linhas de comentário do header.

    Retorna ``None`` quando o campo está ausente ou não é numérico — o registro é
    então descartado do lote pelo chamador (VITALS-08), nunca rotulado por suposição.
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
    """Rótulo de ground truth: ``True`` quando o pH indica acidose (VITALS-02)."""
    return ph < PH_THRESHOLD
