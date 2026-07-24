"""Despacho da análise de um arquivo enviado para o pipeline da sua modalidade.

Não reimplementa detecção: **compõe** as funções que cada pipeline já expõe
(vídeo/postura, áudio/respiração, sinais vitais, prescrição) sobre um único
arquivo e traduz o resultado para uma linguagem clínica, com a pontuação e a
evidência gerada.

Para reaproveitar os pipelines existentes sem alterá-los, os arquivos enviados
têm o mesmo formato dos conjuntos de dados de origem:
- vídeo: um diretório de quadros de uma sequência (padrão UR Fall Detection);
- áudio: uma gravação de ausculta com a anotação de ciclos ao lado (padrão ICBHI);
- sinais vitais: um registro de série temporal (padrão wfdb, ex.: cardiotocografia);
- documento: um PDF de prescrição.

Cada análise devolve um `ResultadoAnalise`: resumo em linguagem clínica, uma
pontuação de 0 a 1 (0 = sem achado; quanto maior, mais preocupante) e o
identificador da evidência gerada (quando há).
"""

from dataclasses import dataclass, field
from pathlib import Path

from common import atividade
from pipelines.prescription.models import PrescriptionRecord

# Tamanho de janela (em quadros) da análise de postura -- mesmo valor calibrado no
# driver da raia de vídeo para as sequências reais de queda.
_JANELA_VIDEO = 30


@dataclass(frozen=True)
class ResultadoAnalise:
    resumo: str
    pontuacao: float | None
    evidencia_id: str | None = None
    detalhes: dict = field(default_factory=dict)


class ErroDeAnalise(Exception):
    """Arquivo enviado incompatível com a modalidade (formato inesperado)."""


# --------------------------------------------------------------------------- #
# Documento (prescrição)
# --------------------------------------------------------------------------- #
def _analisar_documento(
    caminho: Path, prescricao_anterior: PrescriptionRecord | None
) -> ResultadoAnalise:
    from pipelines.prescription.logic import process

    resultado = process(
        Path(caminho).read_bytes(),
        source_id=Path(caminho).name,
        previous_record=prescricao_anterior,
    )

    if resultado.parse_failure is not None:
        return ResultadoAnalise(resumo="Não foi possível ler o documento enviado.", pontuacao=None)

    r = resultado.record
    detalhes = {
        "medicamento": r.drug,
        "dose": r.dose,
        "unidade": r.unit,
        "frequencia": r.frequency,
        "paciente_id_documento": r.patient_id,
        "timestamp_documento": r.timestamp,
    }

    if not resultado.anomalies:
        return ResultadoAnalise(
            resumo=f"{r.drug.capitalize()} {r.dose:g} {r.unit} — sem alteração relevante.",
            pontuacao=0.0,
            detalhes=detalhes,
        )

    motivos = "; ".join(a.reason for a in resultado.anomalies)
    return ResultadoAnalise(
        resumo=f"{r.drug.capitalize()} {r.dose:g} {r.unit} — {motivos}.",
        pontuacao=1.0,
        evidencia_id=resultado.evidence_id,
        detalhes=detalhes | {"anomalias": [a.kind for a in resultado.anomalies]},
    )


# --------------------------------------------------------------------------- #
# Vídeo (postura/queda ou estrutura crítica cirúrgica)
# --------------------------------------------------------------------------- #
def _analisar_video(caminho: Path, run_id: str) -> ResultadoAnalise:
    """Roteia pelo formato do envio: um diretório de quadros é uma sequência de
    postura (padrão UR Fall); um arquivo único é um quadro cirúrgico isolado."""
    caminho = Path(caminho)
    if caminho.is_dir():
        return _analisar_postura(caminho, run_id)
    if caminho.is_file():
        return _analisar_quadro_cirurgico(caminho, run_id)
    raise ErroDeAnalise(f"envio de vídeo não encontrado: {caminho}")


def _analisar_postura(caminho: Path, run_id: str) -> ResultadoAnalise:
    from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_keypoints
    from pipelines.video.pose_detector import (
        DEFAULT_FALL_THRESHOLD,
        classify_sequence,
        save_fall_evidence,
    )
    from pipelines.video.pose_features import windowed_features
    from pipelines.video.pose_loader import load_sequence

    atividade.local("video", "avaliando postura e movimentação com MediaPipe Pose")
    seq = load_sequence(caminho)
    model_path = ensure_pose_model(caminho.parent / "_modelo_pose")
    landmarker = create_landmarker(model_path)
    frames = [extract_keypoints(p, landmarker) for p in seq.frame_paths]
    windows = windowed_features(frames, _JANELA_VIDEO)
    predicted = classify_sequence(windows, DEFAULT_FALL_THRESHOLD)

    if predicted != "queda":
        return ResultadoAnalise(resumo="Sem queda detectada no período monitorado.", pontuacao=0.0)

    evento = next(w for w in windows if w.center_of_mass_amplitude > DEFAULT_FALL_THRESHOLD)
    idx = next(i for i in range(evento.start_frame, evento.end_frame + 1) if frames[i] is not None)
    evidencia = save_fall_evidence(
        seq_id=seq.seq_id,
        frame_path=seq.frame_paths[idx],
        pose_frame=frames[idx],
        event_frame_index=idx,
        score=evento.center_of_mass_amplitude,
        run_id=run_id,
    )
    return ResultadoAnalise(
        resumo="Queda detectada.",
        pontuacao=1.0,
        evidencia_id=evidencia.evidence_id,
        detalhes={"quadro": idx},
    )


_REPO_ROOT = Path(__file__).resolve().parents[2]

# Estruturas anatômicas da via biliar que compõem a "visão crítica de segurança"
# (Critical View of Safety) em colecistectomia — as mesmas de
# `pipelines/video/object_detector.CRITICAL_STRUCTURES`, traduzidas para o nome
# clínico em português usado no resumo.
_TRADUCAO_ESTRUTURA_CRITICA = {
    "cystic_artery": "artéria cística",
    "cystic_duct": "ducto cístico",
    "cystic_plate": "placa cística",
}


def _pesos_yolo() -> Path:
    pesos = _REPO_ROOT / "models" / "best.pt"
    if not pesos.is_file():
        raise ErroDeAnalise(
            "pesos do modelo de detecção de estruturas cirúrgicas ausentes — "
            "rode `make models-fetch`"
        )
    return pesos


def _analisar_quadro_cirurgico(caminho: Path, run_id: str) -> ResultadoAnalise:
    """Raia de estrutura crítica cirúrgica: rótulos de objeto num único quadro,
    via o adaptador `ImageAnalyzer` (YOLOv8 local ou Rekognition, por `ENV`)."""
    from aws.adapters import get_image_analyzer
    from aws.adapters.cloud import register_cloud_adapters
    from aws.clients import resolve_env
    from common.evidence import save_evidence
    from pipelines.video.adapters import register_local_adapters
    from pipelines.video.object_detector import CRITICAL_STRUCTURES

    env = resolve_env()
    if env == "aws":
        register_cloud_adapters()
    else:
        atividade.local("video", "avaliando estrutura cirúrgica crítica no quadro com YOLOv8")
        register_local_adapters(_pesos_yolo())

    analise_imagem = get_image_analyzer(env).analyze(caminho.read_bytes())
    criticas = [rotulo for rotulo in analise_imagem.labels if rotulo.name in CRITICAL_STRUCTURES]

    if not criticas:
        return ResultadoAnalise(
            resumo="Nenhuma estrutura crítica detectada no quadro cirúrgico.",
            pontuacao=0.0,
            detalhes={"caso": "cirurgico"},
        )

    nomes = ", ".join(
        sorted({_TRADUCAO_ESTRUTURA_CRITICA.get(r.name, r.name) for r in criticas})
    )
    evidencia = save_evidence(
        feature="video_object",
        run_id=run_id,
        evidence_id=f"{caminho.stem}-critico",
        source_record_id=caminho.stem,
        artifact_path=caminho,
        metadata={
            "estruturas": [
                {"nome": rotulo.name, "confianca": rotulo.confidence} for rotulo in criticas
            ]
        },
    )
    return ResultadoAnalise(
        resumo=f"Estrutura(s) crítica(s) identificada(s) no quadro cirúrgico: {nomes}.",
        pontuacao=1.0,
        evidencia_id=evidencia.evidence_id,
        detalhes={"caso": "cirurgico"},
    )


# --------------------------------------------------------------------------- #
# Áudio (respiração)
# --------------------------------------------------------------------------- #
_TRADUCAO_RESPIRATORIA = {
    "crackle": "Estertor detectado",
    "wheeze": "Sibilo detectado",
    "both": "Estertor e sibilo detectados",
}


def _analisar_audio(
    caminho: Path, run_id: str, dataset_icbhi: Path, seed: int = 42
) -> ResultadoAnalise:
    from pipelines.audio.icbhi_classifier import predict, train
    from pipelines.audio.icbhi_evidence import save_cycle_evidence
    from pipelines.audio.icbhi_loader import load_cycles, load_dataset, select_subset

    caminho = Path(caminho)
    anotacao = caminho.with_suffix(".txt")
    if not anotacao.is_file():
        raise ErroDeAnalise(
            "a análise de áudio espera a anotação de ciclos (arquivo .txt) ao lado da gravação"
        )

    cycles = load_cycles(anotacao, caminho)
    if not cycles:
        return ResultadoAnalise(
            resumo="Nenhum ciclo respiratório utilizável na gravação.", pontuacao=None
        )

    # Treina o classificador com o conjunto de referência (ICBHI) -- o modelo não é
    # persistido; é treinado sob demanda, como no restante do sistema.
    atividade.local("audio", "classificando ciclos respiratórios (treino sob demanda)")
    referencia, _ = load_dataset(dataset_icbhi)
    por_paciente: dict[str, list] = {}
    for c in referencia:
        por_paciente.setdefault(c.patient_id, []).append(c)
    subconjunto = select_subset(por_paciente, max_patients=40, seed=seed)
    modelo = train(subconjunto, seed=seed)

    predicoes = [(c, predict(modelo, c)) for c in cycles]
    anomalos = [
        (i, c, p) for i, (c, p) in enumerate(predicoes, start=1) if p.predicted_label != "normal"
    ]

    if not anomalos:
        return ResultadoAnalise(resumo="Respiração sem alterações detectadas.", pontuacao=0.0)

    idx, cycle, pred = max(anomalos, key=lambda t: t[2].confidence)
    rotulo = _TRADUCAO_RESPIRATORIA.get(pred.predicted_label, "Alteração respiratória detectada")
    evidencia = save_cycle_evidence(cycle, pred, run_id, "output")
    return ResultadoAnalise(
        resumo=f"{rotulo} no ciclo respiratório {idx} — sugere dificuldade respiratória "
        f"(confiança {pred.confidence:.0%}).",
        pontuacao=float(pred.confidence),
        evidencia_id=evidencia.evidence_id if evidencia is not None else None,
        detalhes={"ciclo": idx, "classe": pred.predicted_label},
    )


# --------------------------------------------------------------------------- #
# Sinais vitais
# --------------------------------------------------------------------------- #
def _canais_do_registro(base: Path) -> list[str]:
    """Nomes dos canais do registro wfdb (sem a vírgula final do cabeçalho BIDMC)."""
    import wfdb

    header = wfdb.rdheader(str(base))
    return [n.strip().rstrip(",") for n in (header.sig_name or [])]


def _analisar_sinais_vitais(caminho: Path, run_id: str) -> ResultadoAnalise:
    caminho = Path(caminho)
    # O wfdb identifica o registro pelo caminho-base (sem extensão).
    base = caminho.with_suffix("") if caminho.suffix in (".hea", ".dat") else caminho

    try:
        canais = _canais_do_registro(base)
    except Exception as exc:
        raise ErroDeAnalise(f"registro de sinais vitais ilegível: {exc}") from exc

    # Dois casos: cardiotocografia (CTU-UHB, canal FHR) e internação adulta
    # (BIDMC, canais HR/SpO2). O caso é escolhido pelos canais presentes.
    if "HR" in canais and "SpO2" in canais:
        return _analisar_internacao(base, run_id)
    if "FHR" in canais:
        return _analisar_cardiotocografia(base, run_id)
    raise ErroDeAnalise(
        f"registro de sinais vitais não reconhecido (canais: {', '.join(canais) or 'nenhum'})"
    )


def _analisar_internacao(base: Path, run_id: str) -> ResultadoAnalise:
    """Caso de internação adulta (BIDMC): HR e SpO2."""
    from pipelines.vitals import bidmc
    from pipelines.vitals.loader import InvalidRecordError

    try:
        record = bidmc.load_numeric_record(base)
    except InvalidRecordError as exc:
        raise ErroDeAnalise(f"registro de internação ilegível: {exc}") from exc

    atividade.local("sinais_vitais", "avaliando HR e SpO2 contra critérios clínicos (BIDMC)")
    achado = bidmc.analisar(record, run_id)
    return ResultadoAnalise(
        resumo=achado.resumo,
        pontuacao=achado.pontuacao,
        evidencia_id=achado.evidencia_id,
        detalhes={"caso": "internacao"},
    )


def _analisar_cardiotocografia(base: Path, run_id: str) -> ResultadoAnalise:
    """Caso de cardiotocografia (CTU-UHB): frequência cardíaca fetal."""
    import dataclasses

    from common.evidence import evidence_dir, save_evidence
    from pipelines.vitals.cli import build_event, evidence_id_de
    from pipelines.vitals.detectors import IsolationForestDetector
    from pipelines.vitals.features import extract
    from pipelines.vitals.loader import InvalidRecordError, load_record
    from pipelines.vitals.plot import plot_anomaly_window
    from pipelines.vitals.preprocess import interpolate_gaps, mark_signal_loss
    from pipelines.vitals.windowing import make_windows

    try:
        record = load_record(base)
    except InvalidRecordError as exc:
        raise ErroDeAnalise(f"registro de sinais vitais ilegível: {exc}") from exc

    mask = mark_signal_loss(record.fhr)
    fhr, mask = interpolate_gaps(record.fhr, mask, max_gap_s=5.0, fs=record.fs)
    limpo = dataclasses.replace(record, fhr=fhr)

    janelas = make_windows(limpo, 600.0, 300.0, mask)
    if not janelas:
        return ResultadoAnalise(resumo="Registro curto demais para avaliar.", pontuacao=None)

    atividade.local("sinais_vitais", "buscando anomalias na série temporal (Isolation Forest)")
    features = [extract(j, fs=limpo.fs) for j in janelas]
    detector = IsolationForestDetector(contamination=0.1, seed=42)
    scores = detector.score(features)
    flags = detector.flag(features)

    anomalas = [(j, s) for j, f, s in zip(janelas, flags, scores, strict=True) if f]
    if not anomalas:
        return ResultadoAnalise(resumo="Sinais vitais sem anomalias no período.", pontuacao=0.0)

    janela, score = max(anomalas, key=lambda t: t[1])
    evento = build_event(limpo, detector.name, janela, score)
    destino = evidence_dir("vitals", run_id, "output")
    destino.mkdir(parents=True, exist_ok=True)
    evidencia_id = evidence_id_de(evento)
    artefato = plot_anomaly_window(limpo, evento, destino / f"{evidencia_id}.png")
    save_evidence(
        feature="vitals",
        run_id=run_id,
        evidence_id=evidencia_id,
        source_record_id=evento.source_record_id,
        artifact_path=artefato,
        metadata=dataclasses.asdict(evento) | {"ph": record.ph},
    )

    ini = int(janela.start_s // 60)
    fim = int(janela.end_s // 60)
    return ResultadoAnalise(
        resumo=f"Anomalia na frequência cardíaca fetal entre {ini} e {fim} minutos.",
        pontuacao=1.0,
        evidencia_id=evidencia_id,
        detalhes={"inicio_min": ini, "fim_min": fim},
    )
