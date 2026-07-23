"""Log de auditoria de toda transição de nível (FUSION-06).

Reaproveita o *princípio* de persistência de `common/metrics.py::save_report` (JSON
indentado, cria os diretórios necessários) -- não importa a função porque ela é
específica de `MetricsReport`.
"""

import json
from dataclasses import asdict
from pathlib import Path

from pipelines.fusion.models import RiskPoint, Transition


def record_transition(previous: str, new: str, point: RiskPoint) -> Transition:
    """Grava nível anterior, novo nível e o `RiskPoint` da transição (que carrega os
    sinais contribuintes em `point.contributions`), para auditoria/explicabilidade."""
    return Transition(t=point.t, previous_level=previous, new_level=new, point=point)


def save_transitions(transitions: list[Transition], path: Path) -> None:
    """Grava as transições como JSON legível, criando os diretórios necessários.

    `default=str` cobre os `Path` reais aninhados em `RiskPoint.contributing_events`
    (evidência real, ver `common/evidence.py::Evidence`), que `json` não serializa
    nativamente.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(t) for t in transitions]
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
