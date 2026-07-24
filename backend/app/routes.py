"""Rotas HTTP da API — pacientes, arquivos enviados, análises, linha do tempo de
risco, alertas e evidências.

Importa `app` de `main.py` e decora as rotas diretamente nele. Este módulo precisa
ser importado (ex.: `from app import routes`) para que as rotas sejam registradas.
"""

import json
import mimetypes
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import armazenamento, repositorio, servico
from app.main import app
from app.schemas import (
    AlertaSchema,
    AnaliseSchema,
    FusionEventSchema,
    PacienteEntrada,
    PacienteSchema,
    RiskPointSchema,
    UploadSchema,
)
from common import atividade
from pipelines.fusion.models import FusionEvent, RiskPoint

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OUTPUT_ROOT = _REPO_ROOT / "output"


# --------------------------------------------------------------------------- #
# Pacientes
# --------------------------------------------------------------------------- #
def _para_paciente_schema(p: repositorio.Paciente) -> PacienteSchema:
    return PacienteSchema(
        id=p.id,
        nome=p.nome,
        data_inicio=p.data_inicio,
        observacoes=p.observacoes,
        nivel_atual=servico.nivel_atual(p.id),
    )


@app.get("/patients", response_model=list[PacienteSchema])
def listar_pacientes() -> list[PacienteSchema]:
    return [_para_paciente_schema(p) for p in repositorio.listar_pacientes()]


@app.post("/patients", response_model=PacienteSchema, status_code=201)
def criar_paciente(entrada: PacienteEntrada) -> PacienteSchema:
    if not entrada.nome.strip():
        raise HTTPException(status_code=422, detail="nome do paciente é obrigatório")
    p = repositorio.criar_paciente(entrada.nome, entrada.data_inicio, entrada.observacoes)
    return _para_paciente_schema(p)


@app.get("/patients/{paciente_id}", response_model=PacienteSchema)
def obter_paciente(paciente_id: str) -> PacienteSchema:
    p = repositorio.obter_paciente(paciente_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")
    return _para_paciente_schema(p)


@app.delete("/patients/{paciente_id}", status_code=204)
def remover_paciente(paciente_id: str) -> None:
    if not repositorio.remover_paciente(paciente_id):
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def _para_upload_schema(u: repositorio.Upload) -> UploadSchema:
    return UploadSchema(
        id=u.id,
        paciente_id=u.paciente_id,
        modalidade=u.modalidade,
        nome_original=u.nome_original,
        criado_em=u.criado_em,
        situacao=u.situacao,
    )


@app.post("/patients/{paciente_id}/uploads", response_model=UploadSchema, status_code=201)
async def enviar_arquivo(
    paciente_id: str, modalidade: str, arquivo: UploadFile = File(...)  # noqa: B008
) -> UploadSchema:
    if repositorio.obter_paciente(paciente_id) is None:
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")
    if modalidade not in repositorio.MODALIDADES:
        raise HTTPException(
            status_code=422,
            detail=f"modalidade inválida: {modalidade!r} "
            f"(esperado uma de {', '.join(repositorio.MODALIDADES)})",
        )
    conteudo = await arquivo.read()
    nome = arquivo.filename or "arquivo"
    caminho = armazenamento.salvar_arquivo(paciente_id, modalidade, nome, conteudo)
    u = repositorio.criar_upload(paciente_id, modalidade, str(caminho), nome)
    atividade.arquivo_recebido(paciente_id, modalidade, nome, len(conteudo))
    return _para_upload_schema(u)


@app.get("/patients/{paciente_id}/uploads", response_model=list[UploadSchema])
def listar_uploads(paciente_id: str) -> list[UploadSchema]:
    if repositorio.obter_paciente(paciente_id) is None:
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")
    return [_para_upload_schema(u) for u in repositorio.listar_uploads(paciente_id)]


# --------------------------------------------------------------------------- #
# Análises
# --------------------------------------------------------------------------- #
def _para_analise_schema(a: repositorio.Analise) -> AnaliseSchema:
    return AnaliseSchema(
        id=a.id,
        upload_id=a.upload_id,
        modalidade=a.modalidade,
        resumo=a.resultado.get("resumo", ""),
        pontuacao=a.pontuacao,
        evidencia_id=a.resultado.get("evidencia_id"),
        criado_em=a.criado_em,
    )


@app.post("/uploads/{upload_id}/analyze", response_model=AnaliseSchema)
def analisar_upload(upload_id: str) -> AnaliseSchema:
    if repositorio.obter_upload(upload_id) is None:
        raise HTTPException(status_code=404, detail=f"envio inexistente: {upload_id}")
    return _para_analise_schema(servico.analisar_upload(upload_id))


@app.get("/uploads/{upload_id}/analysis", response_model=AnaliseSchema)
def resultado_da_analise(upload_id: str) -> AnaliseSchema:
    if repositorio.obter_upload(upload_id) is None:
        raise HTTPException(status_code=404, detail=f"envio inexistente: {upload_id}")
    a = repositorio.obter_analise_de_upload(upload_id)
    if a is None:
        raise HTTPException(status_code=404, detail="envio ainda não foi analisado")
    return _para_analise_schema(a)


# --------------------------------------------------------------------------- #
# Linha do tempo de risco
# --------------------------------------------------------------------------- #
def _para_event_schema(event: FusionEvent) -> FusionEventSchema:
    return FusionEventSchema(
        modality=event.modality,
        demo_timestamp_s=event.demo_timestamp_s,
        severity=event.severity,
        summary=event.summary,
        evidence_id=event.evidence.evidence_id,
    )


def _para_point_schema(point: RiskPoint) -> RiskPointSchema:
    return RiskPointSchema(
        t=point.t,
        score=point.score,
        level=point.level,
        contributions=point.contributions,
        missing_modalities=point.missing_modalities,
        contributing_events=[_para_event_schema(e) for e in point.contributing_events],
    )


@app.get("/patients/{paciente_id}/timeline", response_model=list[RiskPointSchema])
def timeline_do_paciente(paciente_id: str) -> list[RiskPointSchema]:
    if repositorio.obter_paciente(paciente_id) is None:
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")
    return [_para_point_schema(p) for p in servico.linha_do_tempo(paciente_id)]


# --------------------------------------------------------------------------- #
# Alertas
# --------------------------------------------------------------------------- #
def _para_alerta_schema(al: repositorio.Alerta) -> AlertaSchema:
    return AlertaSchema(
        id=al.id,
        paciente_id=al.paciente_id,
        nivel=al.nivel,
        pontuacao=al.pontuacao,
        criado_em=al.criado_em,
        motivo=al.motivo,
        referencias=al.referencias,
    )


@app.get("/patients/{paciente_id}/alerts", response_model=list[AlertaSchema])
def alertas_do_paciente(paciente_id: str) -> list[AlertaSchema]:
    if repositorio.obter_paciente(paciente_id) is None:
        raise HTTPException(status_code=404, detail=f"paciente inexistente: {paciente_id}")
    return [_para_alerta_schema(al) for al in repositorio.listar_alertas_do_paciente(paciente_id)]


@app.get("/alerts", response_model=list[AlertaSchema])
def todos_os_alertas() -> list[AlertaSchema]:
    return [_para_alerta_schema(al) for al in repositorio.listar_todos_os_alertas()]


# --------------------------------------------------------------------------- #
# Evidência
# --------------------------------------------------------------------------- #
def _achar_sidecar(evidence_id: str) -> Path | None:
    if not _OUTPUT_ROOT.is_dir():
        return None
    for sidecar in sorted(_OUTPUT_ROOT.glob(f"*/*/{evidence_id}.json")):
        return sidecar
    return None


@app.get("/evidence/{evidence_id}")
def obter_evidencia(evidence_id: str) -> FileResponse:
    """Serve o artefato real da evidência (imagem/gráfico/documento) pelo seu
    identificador, com os metadados como cabeçalhos HTTP."""
    sidecar_path = _achar_sidecar(evidence_id)
    if sidecar_path is None:
        raise HTTPException(status_code=404, detail=f"evidência inexistente: {evidence_id}")

    raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    artifact_path = sidecar_path.parent / raw["artifact"]
    media_type, _ = mimetypes.guess_type(str(artifact_path))
    return FileResponse(
        path=artifact_path,
        media_type=media_type or "application/octet-stream",
        headers={
            "X-Evidence-Feature": raw["feature"],
            "X-Evidence-Run-Id": raw["run_id"],
            "X-Evidence-Source-Record-Id": raw["source_record_id"],
        },
    )
