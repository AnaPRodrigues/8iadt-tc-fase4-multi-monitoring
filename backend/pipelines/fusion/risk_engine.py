"""Reordenação cronológica cross-modal e cálculo do risk score ponderado por janela de
tempo, com decaimento temporal (FUSION-02, FUSION-03, FUSION-04, FUSION-14).

Eventos de modalidades diferentes podem chegar fora de ordem cronológica -- `sort_events`
normaliza a lista antes de qualquer varredura por janela, para que o motor sempre
processe a timeline em ordem crescente.

`score_at`/`compute_timeline` só calculam o score numérico e as contribuições --
não classificam `RiskPoint.level` (verde/amarelo/vermelho): essa é responsabilidade
exclusiva de `hysteresis.py`, que mantém estado entre janelas (FUSION-05/13) e por isso
não pode ser aplicada aqui ponto a ponto. `level` sai como `""` (não classificado) e é
preenchido pelo chamador que percorre a timeline aplicando o `HysteresisClassifier`.
"""

from pipelines.fusion.config import PatientDemoConfig
from pipelines.fusion.models import FusionEvent, RiskPoint


def sort_events(events: list[FusionEvent]) -> list[FusionEvent]:
    """Reordena os eventos por `demo_timestamp_s`, crescente (FUSION-02)."""
    return sorted(events, key=lambda e: e.demo_timestamp_s)


def decay(elapsed_s: float, half_life_s: float) -> float:
    """Decaimento exponencial: `2 ** (-elapsed_s / half_life_s)`.

    `1.0` em `elapsed_s=0`, cai pela metade a cada `half_life_s` decorridos --
    monotonicamente decrescente conforme `elapsed_s` cresce.
    """
    return 2 ** (-elapsed_s / half_life_s)


def score_at(
    t: float, events: list[FusionEvent], weights: dict[str, float], half_life_s: float
) -> RiskPoint:
    """Soma a contribuição (`peso * severidade * decay`) do evento mais recente de cada
    modalidade configurada em `weights` com `demo_timestamp_s <= t`.

    Modalidade sem nenhum evento até `t` entra em `RiskPoint.missing_modalities`
    (FUSION-04) e não contribui como 0 silenciosamente -- o campo existe justamente
    para tornar essa ausência visível, distinta de uma contribuição calculada como zero.
    """
    mais_recente_por_modalidade: dict[str, FusionEvent] = {}
    for event in sort_events(events):
        if event.demo_timestamp_s <= t:
            mais_recente_por_modalidade[event.modality] = event  # o mais recente vence

    contributions: dict[str, float] = {}
    contributing_events: list[FusionEvent] = []
    missing_modalities: list[str] = []

    for modality, weight in weights.items():
        event = mais_recente_por_modalidade.get(modality)
        if event is None:
            missing_modalities.append(modality)
            continue
        elapsed = t - event.demo_timestamp_s
        contributions[modality] = weight * event.severity * decay(elapsed, half_life_s)
        contributing_events.append(event)

    return RiskPoint(
        t=t,
        score=sum(contributions.values()),
        level="",  # classificado por hysteresis.py, ver docstring do módulo
        contributions=contributions,
        missing_modalities=missing_modalities,
        contributing_events=contributing_events,
    )


def compute_timeline(events: list[FusionEvent], cfg: PatientDemoConfig) -> list[RiskPoint]:
    """Varre de `t=0` até o último `demo_timestamp_s` (+ uma cauda de `window_size_s`),
    em passos de `window_size_s`, calculando um `RiskPoint` por passo.

    Sem eventos, não há o que varrer -- devolve lista vazia.
    """
    if not events:
        return []

    ultimo_t = sort_events(events)[-1].demo_timestamp_s
    fim = ultimo_t + cfg.window_size_s

    pontos: list[RiskPoint] = []
    t = 0.0
    while t <= fim:
        pontos.append(score_at(t, events, cfg.weights, cfg.decay_half_life_s))
        t += cfg.window_size_s

    return pontos
