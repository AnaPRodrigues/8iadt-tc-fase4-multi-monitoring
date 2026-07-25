"""Despacho da análise de um arquivo enviado para o pipeline da sua modalidade.

Não reimplementa detecção: **compõe** as funções que cada pipeline já expõe
(vídeo/postura, áudio, sinais vitais, prescrição) sobre um único
arquivo e traduz o resultado para uma linguagem clínica, com a pontuação e a
evidência gerada.

Para reaproveitar os pipelines existentes sem alterá-los, os arquivos enviados
têm o mesmo formato dos conjuntos de dados de origem:
- vídeo: um ficheiro de vídeo (.mp4, .avi, .mov, .mkv, .webm) para análise de
  postura e movimentação; ou um diretório de quadros de uma sequência (padrão UR
  Fall Detection); ou um quadro cirúrgico isolado (.jpg, .png);
- áudio: uma gravação de ausculta com a anotação de ciclos ao lado (padrão ICBHI)
  ou um áudio de consulta sem anotação (transcrição + features acústicas + termos
  críticos + sentimento);
- sinais vitais: um registro de série temporal (padrão wfdb, ex.: cardiotocografia);
- documento: um PDF de prescrição.

Cada análise devolve um `ResultadoAnalise`: resumo em linguagem clínica, uma
pontuação de 0 a 1 (0 = sem achado; quanto maior, mais preocupante) e o
identificador da evidência gerada (quando há).
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from common import atividade
from pipelines.prescription.models import PrescriptionRecord

# Tamanho de janela (em quadros) da análise de postura -- mesmo valor calibrado no
# driver da raia de vídeo para as sequências reais de queda.
_JANELA_VIDEO = 30

# Extensões reconhecidas como ficheiros de vídeo — são encaminhadas para extração
# de frames e análise de postura/movimentação, não para o detector de estruturas
# cirúrgicas (que espera um único JPEG/PNG).
_EXTENSOES_VIDEO: frozenset[str] = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm"})


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
    """Roteia pelo formato do envio:
    - um diretório de quadros → sequência de postura (padrão UR Fall);
    - um ficheiro de vídeo (.mp4, .avi, …) → extração de frames e análise de
      postura/movimentação;
    - um arquivo de imagem único → quadro cirúrgico (detecção de objetos)."""
    caminho = Path(caminho)
    if caminho.is_dir():
        return _analisar_postura(caminho, run_id)
    if caminho.is_file():
        if caminho.suffix.lower() in _EXTENSOES_VIDEO:
            return _analisar_video_pose(caminho, run_id)
        return _analisar_quadro_cirurgico(caminho, run_id)
    raise ErroDeAnalise(f"envio de vídeo não encontrado: {caminho}")


def _analisar_postura(caminho: Path, run_id: str) -> ResultadoAnalise:
    from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_all_keypoints
    from pipelines.video.pose_detector import (
        classify_with_persistence,
        save_fall_evidence,
    )
    from pipelines.video.pose_features import select_ground_person, windowed_features
    from pipelines.video.pose_loader import load_sequence

    _FALL_THRESHOLD = 0.55

    atividade.local("video", "avaliando postura e movimentação com MediaPipe Pose")
    seq = load_sequence(caminho)
    model_path = ensure_pose_model(caminho.parent / "_modelo_pose")
    landmarker = create_landmarker(model_path, num_poses=3)

    all_poses = [extract_all_keypoints(p, landmarker) for p in seq.frame_paths]
    frames = select_ground_person(all_poses)
    windows = windowed_features(frames, _JANELA_VIDEO)

    fall_verdict, fall_frame_idx = classify_with_persistence(
        windows, _FALL_THRESHOLD, persistence_frames=1,
    )

    if fall_verdict != "queda":
        return ResultadoAnalise(resumo="Sem queda detectada no período monitorado.", pontuacao=0.0)

    evento = next(w for w in windows if w.center_of_mass_amplitude > _FALL_THRESHOLD)
    safe_idx = min(fall_frame_idx or 0, len(seq.frame_paths) - 1, len(frames) - 1)
    if frames[safe_idx] is None:
        return ResultadoAnalise(resumo="Sem queda detectada no período monitorado.", pontuacao=0.0)
    evidencia = save_fall_evidence(
        seq_id=seq.seq_id,
        frame_path=seq.frame_paths[safe_idx],
        pose_frame=frames[safe_idx],
        event_frame_index=safe_idx,
        score=evento.center_of_mass_amplitude,
        run_id=run_id,
        persistence_frames=1,
    )
    return ResultadoAnalise(
        resumo="Queda detectada.",
        pontuacao=float(evento.center_of_mass_amplitude),
        evidencia_id=evidencia.evidence_id,
        detalhes={"quadro": safe_idx},
    )


def _extrair_frames(
    video_path: Path, output_dir: Path, max_frames: int = 500
) -> list[Path]:
    """Extrai frames de um ficheiro de vídeo como PNGs numerados.

    Usa ``cv2.VideoCapture`` para ler o vídeo e ``cv2.imwrite`` para gravar
    cada frame extraído. Vídeos com mais de *max_frames* frames são
    subamostrados uniformemente (ex.: um vídeo de 9000 frames produz no
    máximo 500 PNGs).

    Args:
        video_path: Caminho para o ficheiro de vídeo.
        output_dir: Diretório onde os PNGs serão escritos (criado se não existir).
        max_frames: Limite superior de frames a extrair.

    Returns:
        Lista de caminhos dos PNGs extraídos, ordenados por número de frame.
        Pode ser vazia se o vídeo não contiver frames.

    Raises:
        ErroDeAnalise: Se o ficheiro não existir ou o OpenCV não conseguir
            abri-lo (codec ausente, ficheiro corrompido).
    """
    if not video_path.is_file():
        raise ErroDeAnalise(f"vídeo não encontrado: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise ErroDeAnalise(f"não foi possível abrir o vídeo: {video_path}")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = 1
        if total > max_frames:
            step = max(1, total // max_frames)

        output_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                out = output_dir / f"frame_{len(frame_paths):06d}.png"
                cv2.imwrite(str(out), frame)
                frame_paths.append(out)
            frame_idx += 1
    finally:
        cap.release()

    return frame_paths


def _razao_sem_queda(janelas: list, total_quadros: int) -> str:
    """Devolve texto auxiliar para o resumo quando nenhuma queda é detetada,
    ajudando a distinguir 'não houve queda' de 'não havia pessoa no vídeo'."""
    if not janelas:
        return " Nenhuma pessoa identificada nos quadros analisados."
    return ""


def _analisar_video_pose(caminho: Path, run_id: str) -> ResultadoAnalise:
    """Ficheiro de vídeo → extração de frames → pipeline unificado de pose.

    Executa ambos os detetores (queda com persistência + fisioterapia) sobre
    os mesmos frames extraídos. Com ``num_poses=3``, seleciona automaticamente
    a pessoa mais próxima do chão quando há múltiplos esqueletos na cena.
    """
    from pipelines.video.pose import create_landmarker, ensure_pose_model, extract_all_keypoints
    from pipelines.video.pose_detector import (
        classify_with_persistence,
        detect_postural_deviations,
        detect_trunk_tilt,
        save_fall_evidence,
        save_postural_evidence,
        sumarizar_achados_video,
        validate_fall_dynamic,
    )
    from pipelines.video.pose_features import (
        select_ground_person,
        vertical_velocity,
        windowed_features,
    )

    _FALL_THRESHOLD = 0.55
    _PERSISTENCE_FRAMES = 1
    _NUM_POSES = 3
    _MIN_VERTICAL_VELOCITY = 0.25

    # Extrai frames para um diretório temporário — o pipeline de pose
    # espera PNGs em disco (extract_all_keypoints usa cv2.imread).
    with tempfile.TemporaryDirectory(prefix="video_pose_") as tmp:
        frames_dir = Path(tmp) / "frames"
        frame_paths = _extrair_frames(caminho, frames_dir)

        if not frame_paths:
            return ResultadoAnalise(
                resumo="Vídeo sem quadros utilizáveis para análise de postura.",
                pontuacao=None,
            )

        if len(frame_paths) < _JANELA_VIDEO:
            return ResultadoAnalise(
                resumo=f"Vídeo muito curto para análise de postura "
                f"({len(frame_paths)} quadros, mínimo {_JANELA_VIDEO}).",
                pontuacao=None,
            )

        atividade.local(
            "video",
            f"avaliando postura e movimentação com MediaPipe Pose "
            f"({len(frame_paths)} quadros extraídos do vídeo, "
            f"até {_NUM_POSES} pessoa(s))",
        )

        model_path = ensure_pose_model(caminho.parent / "_modelo_pose")
        landmarker = create_landmarker(model_path, num_poses=_NUM_POSES)

        # Extração multi-pessoa → seleciona pessoa no nível do solo
        all_poses = [extract_all_keypoints(p, landmarker) for p in frame_paths]
        frames = select_ground_person(all_poses)
        n_pessoas = max((len(poses) for poses in all_poses if poses), default=0)

        # Features de movimento (compartilhadas pelos dois detetores)
        windows = windowed_features(frames, _JANELA_VIDEO)

        # --- Deteção de queda (com persistência temporal) ---
        fall_verdict, fall_frame_idx = classify_with_persistence(
            windows, _FALL_THRESHOLD, _PERSISTENCE_FRAMES,
        )

        # Validação dinâmica: exige pico de velocidade vertical para
        # distinguir queda real de postura reclinada estática (falso positivo)
        velocities = vertical_velocity(frames)
        fall_verdict, fall_frame_idx, vy_score, vy_description = (
            validate_fall_dynamic(
                fall_verdict, fall_frame_idx, velocities, _MIN_VERTICAL_VELOCITY,
            )
        )

        todos_detalhes: dict = {
            "quadros_analisados": len(frame_paths),
            "formato": "video",
            "pessoas_detectadas": n_pessoas,
            "vy_max": round(vy_score, 3),
        }
        fall_detected = fall_verdict == "queda" and fall_frame_idx is not None

        # --- Deteção de fisioterapia (desvios + tilt) ---
        fps = 30.0
        postural_findings: list = []
        tilt_findings: list = []

        if not fall_detected:
            from pipelines.video.models import JointTarget
            _DEFAULT_JOINT_TARGETS = [
                JointTarget("knee_left", 23, 25, 27, min_angle=70.0, target_angle=90.0),
                JointTarget("knee_right", 24, 26, 28, min_angle=70.0, target_angle=90.0),
            ]
            postural_findings = detect_postural_deviations(
                frames, _DEFAULT_JOINT_TARGETS, _PERSISTENCE_FRAMES, fps,
            )
            tilt_findings = detect_trunk_tilt(
                frames, max_angle=30.0, persistence_frames=90, fps=fps,
            )

        # --- Sumarização: agrupa por articulação/tipo, score único ---
        resumo, pontuacao, consolidated = sumarizar_achados_video(
            postural_findings, tilt_findings, fall_detected,
        )
        todos_detalhes["findings"] = [c.description for c in consolidated]
        todos_detalhes["n_postural"] = len(postural_findings)
        todos_detalhes["n_tilt"] = len(tilt_findings)
        todos_detalhes["n_consolidated"] = len(consolidated)

        # Se a queda foi rejeitada pelo filtro de velocidade, reporta como postura estática
        postural_rest_note: str | None = None
        if vy_description and fall_verdict != "queda":
            postural_rest_note = vy_description
            todos_detalhes["postural_rest"] = True

        if not consolidated and not fall_detected:
            razao = _razao_sem_queda(windows, len(frame_paths))
            nota = f" {postural_rest_note}" if postural_rest_note else ""
            return ResultadoAnalise(
                resumo=f"Sem alterações detectadas no período monitorado.{razao}{nota}",
                pontuacao=0.0,
                detalhes=todos_detalhes,
            )

        # --- Evidência única consolidada ---
        evidencia_principal: str | None = None
        if fall_detected:
            evento = next(
                w for w in windows if w.center_of_mass_amplitude > _FALL_THRESHOLD
            )
            safe_idx = min(fall_frame_idx or 0, len(frame_paths) - 1, len(frames) - 1)
            if frames[safe_idx] is not None:
                ev = save_fall_evidence(
                    seq_id=caminho.stem,
                    frame_path=frame_paths[safe_idx],
                    pose_frame=frames[safe_idx],
                    event_frame_index=safe_idx,
                    score=evento.center_of_mass_amplitude,
                    run_id=run_id,
                    persistence_frames=_PERSISTENCE_FRAMES,
                )
                evidencia_principal = ev.evidence_id
                todos_detalhes["queda"] = {
                    "frame": safe_idx,
                    "score": round(evento.center_of_mass_amplitude, 3),
                }
        elif consolidated:
            # Um único artefato para o achado mais grave (maior score)
            principal = max(consolidated, key=lambda c: c.score)
            safe_idx = min(principal.frame_index, len(frame_paths) - 1)
            if frames[safe_idx] is not None:
                ev = save_postural_evidence(
                    finding=principal,
                    frame_path=frame_paths[safe_idx],
                    pose_frame=frames[safe_idx],
                    run_id=run_id,
                )
                evidencia_principal = ev.evidence_id

        return ResultadoAnalise(
            resumo=resumo,
            pontuacao=pontuacao,
            evidencia_id=evidencia_principal,
            detalhes=todos_detalhes,
        )


# Intervalo entre keyframes extraídos de um vídeo cirúrgico — a cada 2 segundos
# de vídeo, um frame é analisado pelo YOLOv8. Para um vídeo de 30 s, são ~15
# keyframes (suficiente para cobrir variação de perspetiva sem sobrecarregar).
_INTERVALO_KEYFRAME_S = 2.0


def _analisar_video_cirurgico(caminho: Path, run_id: str) -> ResultadoAnalise:
    """Vídeo cirúrgico (ou quadro único) → YOLOv8 / Rekognition.

    Se for uma imagem (.jpg, .png), analisa como quadro único (mesmo
    comportamento de ``_analisar_quadro_cirurgico``). Se for um ficheiro de
    vídeo, extrai um keyframe a cada ``_INTERVALO_KEYFRAME_S`` segundos e
    agrega as estruturas encontradas ao longo do vídeo.
    """
    if caminho.suffix.lower() not in _EXTENSOES_VIDEO:
        return _analisar_quadro_cirurgico(caminho, run_id)

    from aws.adapters import get_image_analyzer
    from aws.adapters.cloud import register_cloud_adapters
    from aws.clients import resolve_env
    from common.evidence import evidence_dir, save_evidence
    from pipelines.video.adapters import register_local_adapters
    from pipelines.video.object_detector import CRITICAL_STRUCTURES

    # Abre o vídeo uma vez para obter metadados (fps, total de frames).
    cap = cv2.VideoCapture(str(caminho))
    if not cap.isOpened():
        cap.release()
        raise ErroDeAnalise(f"não foi possível abrir o vídeo cirúrgico: {caminho}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    if video_fps <= 0 or total_frames <= 0:
        return ResultadoAnalise(
            resumo="Vídeo cirúrgico sem quadros utilizáveis.", pontuacao=None
        )

    # Keyframe a cada _INTERVALO_KEYFRAME_S segundos.
    step = max(1, int(video_fps * _INTERVALO_KEYFRAME_S))
    keyframe_indices = list(range(0, total_frames, step))
    if not keyframe_indices:
        return ResultadoAnalise(
            resumo="Vídeo cirúrgico muito curto para análise.", pontuacao=None
        )

    # Prepara o analisador de imagem (local ou cloud).
    env = resolve_env()
    if env == "aws":
        register_cloud_adapters()
    else:
        atividade.local(
            "video_cirurgico",
            f"avaliando {len(keyframe_indices)} keyframes do vídeo cirúrgico com YOLOv8",
        )
        register_local_adapters(_pesos_yolo())

    analisador = get_image_analyzer(env)

    # Extrai e analisa cada keyframe.
    cap = cv2.VideoCapture(str(caminho))
    try:
        estruturas_por_keyframe: dict[int, list[str]] = {}
        for kf_idx in keyframe_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, kf_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            # Codifica o frame como JPEG em memória para o analisador.
            _, buf = cv2.imencode(".jpg", frame)
            analise_imagem = analisador.analyze(buf.tobytes())
            criticas = [
                rotulo.name
                for rotulo in analise_imagem.labels
                if rotulo.name in CRITICAL_STRUCTURES
            ]
            if criticas:
                estruturas_por_keyframe[kf_idx] = criticas
    finally:
        cap.release()

    if not estruturas_por_keyframe:
        return ResultadoAnalise(
            resumo="Nenhuma estrutura crítica identificada no vídeo cirúrgico.",
            pontuacao=0.0,
            detalhes={
                "caso": "cirurgico",
                "formato": "video",
                "keyframes_analisados": len(keyframe_indices),
            },
        )

    # Agrega: conjunto de estruturas únicas encontradas ao longo do vídeo.
    todas = sorted({e for lst in estruturas_por_keyframe.values() for e in lst})
    nomes = ", ".join(
        sorted({_TRADUCAO_ESTRUTURA_CRITICA.get(e, e) for e in todas})
    )
    primeiro_kf = min(estruturas_por_keyframe.keys())
    instante = round(primeiro_kf / video_fps, 1)

    # Evidência: extrai o primeiro keyframe com estruturas como PNG.
    primeiro_kf_com_estrutura = min(estruturas_por_keyframe.keys())
    cap2 = cv2.VideoCapture(str(caminho))
    keyframe_png: Path | None = None
    try:
        cap2.set(cv2.CAP_PROP_POS_FRAMES, primeiro_kf_com_estrutura)
        ret, frame = cap2.read()
        if ret:
            destino_kf = evidence_dir("video_object", run_id)
            destino_kf.mkdir(parents=True, exist_ok=True)
            keyframe_png = destino_kf / f"{caminho.stem}-keyframe-{primeiro_kf_com_estrutura}.png"
            cv2.imwrite(str(keyframe_png), frame)
    finally:
        cap2.release()

    if keyframe_png is None or not keyframe_png.is_file():
        return ResultadoAnalise(
            resumo="Não foi possível extrair keyframe para evidência do vídeo cirúrgico.",
            pontuacao=None,
        )

    evidencia = save_evidence(
        feature="video_object",
        run_id=run_id,
        evidence_id=f"{caminho.stem}-cirurgico-video",
        source_record_id=caminho.stem,
        artifact_path=keyframe_png,
        metadata={
            "estruturas": [
                {"nome": e, "keyframes": [k for k, v in estruturas_por_keyframe.items() if e in v]}
                for e in todas
            ],
            "formato": "video",
            "instante_primeiro_s": instante,
        },
    )
    return ResultadoAnalise(
        resumo=f"Estrutura(s) crítica(s) identificada(s) no vídeo cirúrgico "
        f"(aos {instante}s): {nomes}.",
        pontuacao=1.0,
        evidencia_id=evidencia.evidence_id,
        detalhes={
            "caso": "cirurgico",
            "formato": "video",
            "keyframes_analisados": len(keyframe_indices),
            "estruturas": todas,
        },
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
# Áudio (respiração ou consulta)
# --------------------------------------------------------------------------- #
_TRADUCAO_RESPIRATORIA = {
    "crackle": "Estertor detectado",
    "wheeze": "Sibilo detectado",
    "both": "Estertor e sibilo detectados",
}


def _analisar_audio(
    caminho: Path, run_id: str, dataset_icbhi: Path, seed: int = 42
) -> ResultadoAnalise:
    """Dispatcher de áudio: com ``.txt`` de anotação → análise respiratória (ICBHI);
    sem ``.txt`` → análise de consulta (transcrição + acústica + termos críticos +
    sentimento)."""
    caminho = Path(caminho)
    anotacao = caminho.with_suffix(".txt")
    if anotacao.is_file():
        return _analisar_audio_respiratorio(caminho, run_id, dataset_icbhi, seed)
    return _analisar_audio_consulta(caminho, run_id)


def _analisar_audio_respiratorio(
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




def _analisar_audio_consulta(caminho: Path, run_id: str) -> ResultadoAnalise:
    """Áudio de consulta sem anotação: transcrição + features acústicas + fadiga
    vocal + termos críticos + sentimento.

    Com um único áudio o baseline de fadiga é degenerado (desvio-padrão zero) e
    o score é sempre ``0.0`` — mesma limitação documentada no design de F2.
    """
    import json

    from common.evidence import evidence_dir
    from pipelines.audio.acoustic_features import extract as extract_acoustic_features
    from pipelines.audio.critical_terms import find_terms, load_terms, save_term_evidence
    from pipelines.audio.fatigue_score import is_fatigued
    from pipelines.audio.fatigue_score import score as fatigue_score
    from pipelines.audio.sentiment import classify as classify_sentiment
    from pipelines.audio.transcribe import transcribe

    caminho = Path(caminho)

    atividade.local("audio", "transcrevendo áudio de consulta com faster-whisper")
    try:
        transcript = transcribe(caminho, model_size="small", no_speech_threshold=0.6)
    except Exception as exc:
        raise ErroDeAnalise(f"não foi possível transcrever o áudio: {exc}") from exc

    if not transcript.reliable:
        return ResultadoAnalise(
            resumo="Não foi possível obter uma transcrição confiável do áudio de consulta.",
            pontuacao=None,
            detalhes={"motivo": "transcricao_nao_confiavel"},
        )

    atividade.local("audio", "extraindo features acústicas (jitter, shimmer, HNR)")
    try:
        features = extract_acoustic_features(caminho, transcript)
    except Exception as exc:
        raise ErroDeAnalise(f"não foi possível extrair features acústicas: {exc}") from exc

    # Score de fadiga com baseline de 1 áudio (z-score = 0.0 por construção —
    # desvio-padrão zero). A heurística é documentada como limitada no design de F2.
    fadiga = fatigue_score(features, baseline=[features])
    fatigado = is_fatigued(fadiga, threshold=1.0)

    sentimento = classify_sentiment(transcript.text, threshold=0.2)

    termos = load_terms(None)
    hits = find_terms(transcript, termos)

    # Evidência
    destino = evidence_dir("audio", run_id, "output")
    destino.mkdir(parents=True, exist_ok=True)
    stem = caminho.stem
    evidencia_id = None

    # Guarda um artefato com o transcript completo
    artefato_txt = destino / f"{stem}-transcript.txt"
    artefato_txt.write_text(transcript.text, encoding="utf-8")

    if hits:
        for hit in hits:
            ev = save_term_evidence(hit, transcript, run_id, "output")
            if evidencia_id is None:
                evidencia_id = ev.evidence_id

    # Sidecar de metadados da consulta (contrato AD-026)
    metadados = {
        "sentimento": sentimento.label,
        "sentimento_score": round(sentimento.score, 3),
        "termos_criticos_encontrados": len(hits),
        "fadiga_vocal_score": round(fadiga, 3),
        "fadiga_vocal_detectada": fatigado,
        "transcript_confiavel": transcript.reliable,
    }
    (destino / f"{stem}-summary.json").write_text(
        json.dumps(metadados, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Monta resumo clínico
    partes: list[str] = []

    if hits:
        termos_encontrados = ", ".join(sorted({h.term for h in hits}))
        partes.append(f"termo(s) crítico(s) encontrado(s): {termos_encontrados}")

    if sentimento.label != "neutro":
        partes.append(f"sentimento {sentimento.label}")

    if not partes:
        return ResultadoAnalise(
            resumo="Áudio de consulta sem alterações relevantes detectadas.",
            pontuacao=0.0,
            detalhes=metadados,
        )

    # Pontuação heurística: termos críticos + fadiga
    pontuacao = 0.0
    if hits:
        pontuacao = max(pontuacao, 0.5 + min(len(hits) * 0.1, 0.5))
    if fatigado:
        pontuacao = max(pontuacao, 0.7)

    resumo = " | ".join(partes) + "."

    return ResultadoAnalise(
        resumo=resumo.capitalize(),
        pontuacao=pontuacao,
        evidencia_id=evidencia_id,
        detalhes=metadados,
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
