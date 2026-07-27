"""Camada de serviço: liga os arquivos enviados aos pipelines de análise e
monta a linha do tempo de risco do paciente a partir do banco local.

- `analisar_upload` roda a análise da modalidade do arquivo (reaproveitando os
  pipelines via `app.analise`), grava o resultado e reavalia os alertas.
- `linha_do_tempo` converte as análises do paciente em eventos e roda o motor de
  fusão de risco já existente (peso, decaimento, histerese) sobre eles.
"""

import os
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from app import analise, repositorio
from app.analise import ResultadoAnalise
from common import atividade
from common.evidence import Evidence
from pipelines.fusion.config import DEFAULTS
from pipelines.fusion.hysteresis import VERDE, HysteresisClassifier
from pipelines.fusion.models import FusionEvent, RiskPoint
from pipelines.fusion.risk_engine import compute_timeline

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_ROOT = _REPO_ROOT / "output"

# Modalidade no banco -> modalidade no motor de fusão (que usa os nomes das análises).
_MODALIDADE_FUSAO = {
    "video": "video",
    "video_cirurgico": "video",
    "audio": "audio",
    "documento": "prescription",
    "sinais_vitais": "vitals",
}


def _dataset_icbhi() -> Path:
    """Conjunto de referência para treinar o classificador respiratório sob demanda."""
    env = os.environ.get("ICBHI_DATASET_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"


@dataclass(frozen=True)
class ParametrosRisco:
    """Parâmetros do motor de risco: pesos por modalidade, decaimento, tamanho da
    janela, limiares de nível e o nível que dispara um alerta."""

    weights: dict[str, float]
    decay_half_life_s: float
    window_size_s: float
    threshold_amarelo: float
    threshold_vermelho: float
    hysteresis: float
    alert_level: str


def _config_risco() -> ParametrosRisco:
    """Parâmetros do motor de risco, a partir dos padrões documentados."""
    return ParametrosRisco(
        weights=DEFAULTS["weights"],
        decay_half_life_s=DEFAULTS["decay_half_life_s"],
        window_size_s=DEFAULTS["window_size_s"],
        threshold_amarelo=DEFAULTS["threshold_amarelo"],
        threshold_vermelho=DEFAULTS["threshold_vermelho"],
        hysteresis=DEFAULTS["hysteresis"],
        alert_level=DEFAULTS["alert_level"],
    )


# --------------------------------------------------------------------------- #
# Disparo de análise de um upload
# --------------------------------------------------------------------------- #
def _prescricao_anterior(paciente_id: str, upload_atual_id: str):
    """Prescrição mais recente do paciente já analisada (para a regra de variação
    abrupta) -- reconstruída a partir do resultado guardado no banco."""
    from pipelines.prescription.models import PrescriptionRecord

    for a in reversed(repositorio.listar_analises_do_paciente(paciente_id)):
        if a.modalidade != "documento" or a.upload_id == upload_atual_id:
            continue
        d = a.resultado.get("detalhes", {})
        if "medicamento" in d:
            return PrescriptionRecord(
                patient_id=d.get("paciente_id_documento", paciente_id),
                drug=d["medicamento"],
                dose=float(d["dose"]),
                unit=d["unidade"],
                frequency=d.get("frequencia", ""),
                timestamp=d.get("timestamp_documento", ""),
            )
    return None


def analisar_upload(upload_id: str, *, instante_s: float | None = None) -> repositorio.Analise:
    """Roda a análise da modalidade do arquivo enviado, grava o resultado e
    reavalia os alertas do paciente. Marca a situação do upload ao longo do caminho.

    ``instante_s`` fixa explicitamente a posição do evento na linha do tempo (em
    segundos desde o início do monitoramento) — usado pela carga inicial de
    demonstração para compor uma narrativa; sem ele, `_instante_s` cai no tempo
    real decorrido entre o início do monitoramento e a análise."""
    upload = repositorio.obter_upload(upload_id)
    if upload is None:
        raise ValueError(f"upload inexistente: {upload_id}")

    repositorio.atualizar_situacao_upload(upload_id, "processando")
    caminho = Path(upload.caminho)
    atividade.analise_iniciada(upload.paciente_id, upload.modalidade)
    inicio = time.monotonic()
    try:
        resultado = _despachar(upload, caminho)
    except analise.ErroDeAnalise as exc:
        atividade.analise_falhou(upload.modalidade, str(exc))
        repositorio.atualizar_situacao_upload(upload_id, "erro")
        resultado = ResultadoAnalise(
            resumo=f"Não foi possível analisar o arquivo: {exc}", pontuacao=None
        )
        registro = repositorio.criar_analise(
            upload_id, upload.modalidade, _para_dict(resultado), None
        )
        return registro

    if instante_s is not None:
        resultado = replace(resultado, detalhes=resultado.detalhes | {"instante_s": instante_s})

    atividade.analise_concluida(upload.modalidade, time.monotonic() - inicio, resultado.resumo)
    registro = repositorio.criar_analise(
        upload_id, upload.modalidade, _para_dict(resultado), resultado.pontuacao
    )
    repositorio.atualizar_situacao_upload(upload_id, "concluido")

    _reavaliar_alertas(upload.paciente_id)
    return registro


def _despachar(upload: repositorio.Upload, caminho: Path) -> ResultadoAnalise:
    run_id = upload.id
    if upload.modalidade == "documento":
        anterior = _prescricao_anterior(upload.paciente_id, upload.id)
        return analise._analisar_documento(caminho, anterior)
    if upload.modalidade == "video":
        return analise._analisar_video(caminho, run_id)
    if upload.modalidade == "video_cirurgico":
        return analise._analisar_video_cirurgico(caminho, run_id)
    if upload.modalidade == "audio":
        return analise._analisar_audio(caminho, run_id, _dataset_icbhi())
    if upload.modalidade == "sinais_vitais":
        return analise._analisar_sinais_vitais(caminho, run_id)
    raise analise.ErroDeAnalise(f"modalidade desconhecida: {upload.modalidade}")


def _para_dict(resultado: ResultadoAnalise) -> dict:
    return {
        "resumo": resultado.resumo,
        "pontuacao": resultado.pontuacao,
        "evidencia_id": resultado.evidencia_id,
        "detalhes": resultado.detalhes,
    }


# --------------------------------------------------------------------------- #
# Linha do tempo de risco do paciente
# --------------------------------------------------------------------------- #
def _instante_s(paciente: repositorio.Paciente, a: repositorio.Analise) -> float:
    """Posição do evento na linha do tempo, em segundos desde o início do
    monitoramento. Um `instante_s` explícito no resultado tem prioridade (usado
    pela carga de demonstração para compor uma narrativa)."""
    explicito = a.resultado.get("detalhes", {}).get("instante_s")
    if explicito is not None:
        return float(explicito)
    try:
        inicio = datetime.fromisoformat(paciente.data_inicio)
        criado = datetime.fromisoformat(a.criado_em)
        return max(0.0, (criado - inicio).total_seconds())
    except ValueError:
        return 0.0


def _carregar_evidencia(evidencia_id: str) -> Evidence | None:
    if not _OUTPUT_ROOT.is_dir():
        return None
    import json

    for sidecar in sorted(_OUTPUT_ROOT.glob(f"*/*/{evidencia_id}.json")):
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        return Evidence(
            feature=raw["feature"],
            run_id=raw["run_id"],
            evidence_id=raw["evidence_id"],
            source_record_id=raw["source_record_id"],
            artifact_path=sidecar.parent / raw["artifact"],
            sidecar_path=sidecar,
        )
    return None


def _eventos_do_paciente(paciente: repositorio.Paciente) -> list[FusionEvent]:
    """Converte as análises com achado (pontuação > 0 e evidência) em eventos de
    fusão. Análises sem anomalia não contribuem para o risco."""
    eventos: list[FusionEvent] = []
    for a in repositorio.listar_analises_do_paciente(paciente.id):
        if not a.pontuacao or a.resultado.get("evidencia_id") is None:
            continue
        evidencia = _carregar_evidencia(a.resultado["evidencia_id"])
        if evidencia is None:
            continue
        eventos.append(
            FusionEvent(
                modality=_MODALIDADE_FUSAO.get(a.modalidade, a.modalidade),
                demo_timestamp_s=_instante_s(paciente, a),
                severity=float(a.pontuacao),
                summary=a.resultado.get("resumo", ""),
                evidence=evidencia,
            )
        )
    return eventos


def linha_do_tempo(paciente_id: str) -> list[RiskPoint]:
    """Roda o motor de fusão sobre os eventos do paciente e classifica cada ponto."""
    paciente = repositorio.obter_paciente(paciente_id)
    if paciente is None:
        raise ValueError(f"paciente inexistente: {paciente_id}")

    eventos = _eventos_do_paciente(paciente)
    if not eventos:
        return []

    cfg = _config_risco()
    pontos = compute_timeline(eventos, cfg)
    classificador = HysteresisClassifier(
        cfg.threshold_amarelo, cfg.threshold_vermelho, cfg.hysteresis
    )
    return [replace(p, level=classificador.update(p.score)) for p in pontos]


def nivel_atual(paciente_id: str) -> str:
    """Nível de risco corrente do paciente (verde se não há evento)."""
    pontos = linha_do_tempo(paciente_id)
    return pontos[-1].level if pontos else VERDE


# --------------------------------------------------------------------------- #
# Alertas
# --------------------------------------------------------------------------- #
def _reavaliar_alertas(paciente_id: str) -> None:
    """Registra um alerta quando a linha do tempo cruza o nível de disparo, sem
    duplicar um alerta já registrado para o mesmo conjunto de evidências."""
    cfg = _config_risco()
    pontos = linha_do_tempo(paciente_id)

    ja_registrados = {
        tuple(sorted(al.referencias)) for al in repositorio.listar_alertas_do_paciente(paciente_id)
    }

    nivel_anterior = VERDE
    score_anterior = 0.0
    for ponto in pontos:
        if ponto.level != nivel_anterior:
            atividade.risco(score_anterior, ponto.score, ponto.level)
        if ponto.level != nivel_anterior and ponto.level == cfg.alert_level:
            referencias = sorted(e.evidence.evidence_id for e in ponto.contributing_events)
            if tuple(referencias) not in ja_registrados:
                motivo = _motivo_clinico(ponto)
                repositorio.registrar_alerta(
                    paciente_id, ponto.level, round(ponto.score, 2), motivo, referencias
                )
                ja_registrados.add(tuple(referencias))
                atividade.alerta_registrado(paciente_id, motivo)
        nivel_anterior = ponto.level
        score_anterior = ponto.score


def _motivo_clinico(ponto: RiskPoint) -> str:
    """Motivo do alerta em linguagem clínica, juntando os resumos das modalidades
    que contribuíram."""
    return " + ".join(e.summary for e in ponto.contributing_events) or "risco elevado"
