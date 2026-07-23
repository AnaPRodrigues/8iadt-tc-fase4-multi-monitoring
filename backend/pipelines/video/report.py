"""Relatório Markdown consolidado por sequência/vídeo.

`ReportEvent` é definido aqui -- nenhum outro módulo produz um registro de
"evento pronto para relatório" (frame + tipo + link de evidência); as duas
raias produzem tipos diferentes (`SequenceVerdict`/`Evidence` na pose,
`Detection`/`Evidence` no objeto), então o chamador de cada raia traduz seu
resultado para `ReportEvent` antes de chamar `generate_report`.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReportEvent:
    frame: int
    kind: str  # "queda" | "estrutura_critica"
    evidence_path: Path


def _render_event(event: ReportEvent) -> str:
    return f"- Frame {event.frame} — {event.kind} — evidência: `{event.evidence_path}`"


def generate_report(
    pose_result: list[ReportEvent], object_result: list[ReportEvent] | None = None
) -> str:
    """Gera o relatório Markdown consolidando eventos das duas raias.

    Nenhum evento nas duas raias -> relatório indica explicitamente "nenhum
    evento detectado", nunca omitido. Função pura -- não lê nem
    grava estado global, então sequências/vídeos processados em chamadas
    sucessivas nunca se misturam.
    """
    events = list(pose_result) + list(object_result or [])

    linhas = ["# Relatório de eventos"]
    if not events:
        linhas.append("Nenhum evento detectado.")
    else:
        linhas.extend(_render_event(event) for event in events)

    return "\n".join(linhas)
