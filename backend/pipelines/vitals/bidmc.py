"""Segundo caso de sinais vitais: internação adulta (BIDMC).

O conjunto BIDMC traz sinais numéricos de monitor de UTI a 1 Hz — frequência
cardíaca (HR) e saturação de oxigênio (SpO2), entre outros. Esses numéricos ficam
em registros SEPARADOS, com sufixo ``n`` no nome (ex.: ``bidmc01n``), que não
constam da listagem principal do conjunto — são eles que interessam aqui.

Diferente da cardiotocografia (CTU-UHB), o BIDMC **não vem com desfecho anotado**.
Por isso a avaliação usa **critérios clínicos publicados** como referência
(ver `CRITERIOS_CLINICOS`), não um rótulo do conjunto de dados.

A detecção **reaproveita os detectores já existentes** (escore móvel e floresta de
isolamento, `pipelines/vitals/detectors.py`) e a extração de features por janela
(`pipelines/vitals/features.py`) — este módulo só adapta a leitura do sinal e a
referência clínica; não reimplementa detecção.
"""

from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import wfdb

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from common.evidence import Evidence, evidence_dir, save_evidence  # noqa: E402
from common.logging import get_logger  # noqa: E402
from pipelines.vitals.detectors import IsolationForestDetector, RollingZScoreDetector  # noqa: E402
from pipelines.vitals.features import extract  # noqa: E402
from pipelines.vitals.loader import InvalidRecordError, Segment, VitalRecord  # noqa: E402
from pipelines.vitals.windowing import make_windows  # noqa: E402

log = get_logger("vitals.bidmc")

# --------------------------------------------------------------------------- #
# Critérios clínicos de referência (num único lugar, configuráveis).
#
# Fontes: saturação de oxigênio (SpO2) abaixo de 90% de forma sustentada
# caracteriza hipoxemia; frequência cardíaca (HR) em repouso fora da faixa de
# 60 a 100 bpm caracteriza bradicardia (<60) ou taquicardia (>100). São faixas de
# referência clínica amplamente adotadas (ex.: diretrizes de sinais vitais de
# adultos) — usadas aqui apenas como referência de avaliação, não como diagnóstico.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CriteriosClinicos:
    spo2_hipoxemia: float = 90.0  # SpO2 abaixo disso, sustentada, é hipoxemia
    hr_min: float = 60.0  # HR abaixo disso é bradicardia
    hr_max: float = 100.0  # HR acima disso é taquicardia
    fracao_sustentada: float = 0.5  # fração mínima da janela para "sustentado"


CRITERIOS_CLINICOS = CriteriosClinicos()

# Nomes dos canais no registro numérico (o cabeçalho do BIDMC traz vírgula no fim).
_CANAL_HR = "HR"
_CANAL_SPO2 = "SpO2"


@dataclass(frozen=True)
class BidmcRecord:
    record_id: str
    hr: np.ndarray
    spo2: np.ndarray
    fs: float


def _canal(record, alvo: str) -> np.ndarray:
    """Localiza o canal pelo nome, tolerando a vírgula final do cabeçalho BIDMC."""
    nomes = [n.strip().rstrip(",") for n in (record.sig_name or [])]
    if alvo not in nomes:
        raise InvalidRecordError(f"canal {alvo} ausente no registro {record.record_name}")
    coluna = nomes.index(alvo)
    return np.asarray(record.p_signal[:, coluna], dtype=float)


def load_numeric_record(record_path: Path) -> BidmcRecord:
    """Lê um registro numérico do BIDMC (``bidmcNNn``) e expõe HR e SpO2 a 1 Hz.

    ``record_path`` é o caminho-base do registro (sem extensão) — o wfdb resolve
    ``.hea``/``.dat`` a partir dele.
    """
    try:
        record = wfdb.rdrecord(str(record_path))
    except Exception as exc:  # wfdb levanta tipos variados
        raise InvalidRecordError(f"falha ao ler {record_path}: {exc}") from exc

    return BidmcRecord(
        record_id=record.record_name or Path(record_path).name,
        hr=_canal(record, _CANAL_HR),
        spo2=_canal(record, _CANAL_SPO2),
        fs=float(record.fs),
    )


def _como_registro(record_id: str, sinal: np.ndarray, fs: float) -> tuple[VitalRecord, np.ndarray]:
    """Embrulha um sinal 1-D no formato que o janelamento já consome e devolve a
    máscara de validade (amostra ausente = NaN ou <= 0)."""
    sinal = np.asarray(sinal, dtype=float)
    mask = np.isnan(sinal) | (sinal <= 0)
    registro = VitalRecord(
        record_id=record_id,
        fhr=sinal,  # o janelamento/feature operam sobre este canal genérico
        uc=np.zeros_like(sinal),  # não usado pela extração de features
        fs=fs,
        ph=float("nan"),  # BIDMC não tem desfecho anotado
        provenance=[Segment(source_record_id=record_id, start_idx=0, end_idx=len(sinal))],
    )
    return registro, mask


# --------------------------------------------------------------------------- #
# Referência clínica por janela (ground truth da avaliação)
# --------------------------------------------------------------------------- #
def _hr_anomala(janela: np.ndarray, crit: CriteriosClinicos) -> bool:
    validos = janela[~np.isnan(janela) & (janela > 0)]
    if validos.size == 0:
        return False
    mediana = float(np.median(validos))
    return mediana < crit.hr_min or mediana > crit.hr_max


def _spo2_anomala(janela: np.ndarray, crit: CriteriosClinicos) -> bool:
    validos = janela[~np.isnan(janela) & (janela > 0)]
    if validos.size == 0:
        return False
    fracao_baixa = float(np.mean(validos < crit.spo2_hipoxemia))
    return fracao_baixa >= crit.fracao_sustentada


@dataclass(frozen=True)
class ResultadoSinal:
    sinal: str  # "HR" | "SpO2"
    n_janelas: int
    n_eventos_clinicos: int
    precision: float
    recall: float
    f1: float
    primeira_janela_anomala: tuple[float, float] | None  # (start_s, end_s) ou None


def _metricas(preditos: list[bool], reais: list[bool]) -> tuple[float, float, float]:
    tp = sum(p and r for p, r in zip(preditos, reais, strict=True))
    fp = sum(p and not r for p, r in zip(preditos, reais, strict=True))
    fn = sum((not p) and r for p, r in zip(preditos, reais, strict=True))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def avaliar_sinal(
    record_id: str,
    sinal: np.ndarray,
    nome_sinal: str,
    fs: float,
    *,
    size_s: float = 60.0,
    stride_s: float = 30.0,
    zscore_threshold: float = 3.0,
    iforest_contamination: float = 0.1,
    seed: int = 42,
    criterio_anomalo=None,
    crit: CriteriosClinicos = CRITERIOS_CLINICOS,
) -> ResultadoSinal:
    """Janela o sinal, roda os detectores existentes e compara com a referência
    clínica. O detector usado como predição é a floresta de isolamento (multivariada
    sobre as features da janela); o escore móvel também é executado e serve de
    reforço. A referência (ground truth) vem de ``criterio_anomalo`` (clínico)."""
    registro, mask = _como_registro(record_id, sinal, fs)
    janelas = make_windows(registro, size_s, stride_s, mask)
    if not janelas:
        return ResultadoSinal(nome_sinal, 0, 0, 0.0, 0.0, 0.0, None)

    features = [extract(j, fs=fs) for j in janelas]
    iforest = IsolationForestDetector(contamination=iforest_contamination, seed=seed)
    zscore = RollingZScoreDetector(threshold=zscore_threshold)
    flags_if = iforest.flag(features)
    flags_z = zscore.flag(features)

    reais = [criterio_anomalo(j.fhr, crit) for j in janelas]
    # predição: anômalo se qualquer detector sinalizar (janela inválida = não anômala)
    preditos = [
        bool((fi is True) or (fz is True)) for fi, fz in zip(flags_if, flags_z, strict=True)
    ]

    precision, recall, f1 = _metricas(preditos, reais)
    primeira = next(
        ((j.start_s, j.end_s) for j, r in zip(janelas, reais, strict=True) if r), None
    )
    return ResultadoSinal(
        sinal=nome_sinal,
        n_janelas=len(janelas),
        n_eventos_clinicos=sum(reais),
        precision=precision,
        recall=recall,
        f1=f1,
        primeira_janela_anomala=primeira,
    )


def avaliar_registro(record: BidmcRecord, **kwargs) -> list[ResultadoSinal]:
    """Avalia HR e SpO2 de um registro contra os critérios clínicos."""
    return [
        avaliar_sinal(
            record.record_id, record.hr, "HR", record.fs, criterio_anomalo=_hr_anomala, **kwargs
        ),
        avaliar_sinal(
            record.record_id,
            record.spo2,
            "SpO2",
            record.fs,
            criterio_anomalo=_spo2_anomala,
            **kwargs,
        ),
    ]


# --------------------------------------------------------------------------- #
# Varredura utilitária dos 53 registros (para escolher casos de demonstração)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RegistroComEventos:
    record_id: str
    eventos_hr: int
    eventos_spo2: int


def varrer(
    dataset_dir: Path, crit: CriteriosClinicos = CRITERIOS_CLINICOS
) -> list[RegistroComEventos]:
    """Percorre os registros numéricos (``*n``) e lista quantos eventos clínicos
    (HR fora de faixa; SpO2 em hipoxemia) cada um contém. Útil para escolher casos
    de demonstração — **seleciona** registros com eventos, sem alterar os sinais."""
    dataset_dir = Path(dataset_dir)
    achados: list[RegistroComEventos] = []
    for hea in sorted(dataset_dir.glob("*n.hea")):
        try:
            record = load_numeric_record(hea.with_suffix(""))
        except InvalidRecordError as exc:
            log.warning("registro %s ignorado: %s", hea.name, exc)
            continue
        resultados = {r.sinal: r for r in avaliar_registro(record, crit=crit)}
        achados.append(
            RegistroComEventos(
                record_id=record.record_id,
                eventos_hr=resultados["HR"].n_eventos_clinicos,
                eventos_spo2=resultados["SpO2"].n_eventos_clinicos,
            )
        )
    return achados


# --------------------------------------------------------------------------- #
# Evidência e resumo clínico (para a análise de um upload)
# --------------------------------------------------------------------------- #
def plot_janela(
    record_id: str,
    nome_sinal: str,
    unidade: str,
    serie: np.ndarray,
    fs: float,
    inicio_s: float,
    fim_s: float,
    out_path: Path,
) -> Path:
    """Plota o sinal inteiro com a janela anômala destacada e grava em ``out_path``."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tempo = [i / fs for i in range(len(serie))]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(tempo, serie, linewidth=0.8, color="#1f77b4")
    ax.axvspan(inicio_s, fim_s, color="#d62728", alpha=0.25, label="trecho anômalo")
    ax.set_title(f"{record_id} — {nome_sinal}")
    ax.set_xlabel("tempo (s)")
    ax.set_ylabel(f"{nome_sinal} ({unidade})")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return out_path


@dataclass(frozen=True)
class AchadoBidmc:
    resumo: str
    pontuacao: float
    evidencia_id: str | None
    evidencia: Evidence | None


def _minutos(inicio_s: float, fim_s: float) -> str:
    return f"entre {int(inicio_s // 60)} e {int(fim_s // 60)} minutos"


def analisar(record: BidmcRecord, run_id: str, root: str | Path = "output") -> AchadoBidmc:
    """Analisa HR e SpO2 de um registro de internação e devolve o achado mais
    relevante em linguagem clínica, com a evidência gerada.

    Prioriza a hipoxemia (SpO2 < 90%) sobre a alteração de frequência cardíaca —
    a dessaturação é o sinal mais urgente. Sem achado, devolve pontuação 0.
    """
    resultados = {r.sinal: r for r in avaliar_registro(record)}
    spo2 = resultados["SpO2"]
    hr = resultados["HR"]

    if spo2.n_eventos_clinicos and spo2.primeira_janela_anomala:
        inicio, fim = spo2.primeira_janela_anomala
        resumo = f"Saturação de oxigênio abaixo de 90% (hipoxemia) {_minutos(inicio, fim)}."
        return _com_evidencia(record, "SpO2", "%", record.spo2, inicio, fim, resumo, run_id, root)

    if hr.n_eventos_clinicos and hr.primeira_janela_anomala:
        inicio, fim = hr.primeira_janela_anomala
        n_ini = int(inicio * record.fs)
        n_fim = int(fim * record.fs)
        trecho = record.hr[n_ini:n_fim]
        validos = trecho[~np.isnan(trecho) & (trecho > 0)]
        mediana = float(np.median(validos)) if validos.size else 0.0
        tipo = "taquicardia" if mediana > CRITERIOS_CLINICOS.hr_max else "bradicardia"
        resumo = f"Frequência cardíaca fora da faixa 60–100 bpm ({tipo}) {_minutos(inicio, fim)}."
        return _com_evidencia(record, "HR", "bpm", record.hr, inicio, fim, resumo, run_id, root)

    return AchadoBidmc(
        resumo="Sinais vitais de internação (HR/SpO2) sem alterações no período.",
        pontuacao=0.0,
        evidencia_id=None,
        evidencia=None,
    )


def _com_evidencia(
    record: BidmcRecord,
    nome_sinal: str,
    unidade: str,
    serie: np.ndarray,
    inicio_s: float,
    fim_s: float,
    resumo: str,
    run_id: str,
    root: str | Path,
) -> AchadoBidmc:
    destino = evidence_dir("vitals", run_id, root)
    evidencia_id = f"{record.record_id}-{nome_sinal.lower()}-{int(inicio_s)}s"
    artefato = plot_janela(
        record.record_id, nome_sinal, unidade, serie, record.fs, inicio_s, fim_s,
        destino / f"{evidencia_id}.png",
    )
    # SpO2 < 90% é emergência clínica → CRITICAL; HR fora da faixa → MEDIUM
    severidade = "CRITICAL" if nome_sinal == "SpO2" else "MEDIUM"
    evidencia = save_evidence(
        feature="vitals",
        run_id=run_id,
        evidence_id=evidencia_id,
        source_record_id=record.record_id,
        artifact_path=artefato,
        metadata={"sinal": nome_sinal, "inicio_s": inicio_s, "fim_s": fim_s, "resumo": resumo},
        root=root,
        severity=severidade,
    )
    return AchadoBidmc(
        resumo=resumo,
        pontuacao=1.0,
        evidencia_id=evidencia.evidence_id,
        evidencia=evidencia,
    )


# --------------------------------------------------------------------------- #
# Uso como script: varredura dos registros para escolher casos de demonstração
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Varre os registros numéricos do BIDMC e lista quais contêm eventos "
        "clínicos (HR fora de 60–100 bpm; SpO2 sustentada < 90%). Não altera os sinais."
    )
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/bidmc"))
    args = parser.parse_args(argv)

    achados = varrer(args.dataset_dir)
    com_eventos = [a for a in achados if a.eventos_hr or a.eventos_spo2]
    print(f"{len(achados)} registro(s) avaliado(s); {len(com_eventos)} com evento clínico:\n")
    print(f"{'registro':<12} {'eventos HR':>11} {'eventos SpO2':>13}")
    for a in sorted(com_eventos, key=lambda x: x.eventos_hr + x.eventos_spo2, reverse=True):
        print(f"{a.record_id:<12} {a.eventos_hr:>11} {a.eventos_spo2:>13}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
