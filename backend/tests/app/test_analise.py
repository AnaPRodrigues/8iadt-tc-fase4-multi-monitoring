"""Testes do despacho de análise (composição dos pipelines sobre um arquivo).

- Documento: rápido, com PDF sintético gerado (sem conjunto de dados externo).
- Vídeo (ficheiro .mp4): frame sintético com cv2.VideoWriter, sem dependência de
  datasets externos.
- Vídeo / sinais vitais: integração contra os conjuntos de dados reais; pulam com
  mensagem clara se o dataset não estiver presente (``make data``).
"""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app import analise
from aws.adapters import ImageAnalysis, ImageLabel
from pipelines.prescription.generator import generate_prescription
from pipelines.prescription.models import PrescriptionRecord

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _gerar_mp4_sintetico(destino: Path, n_frames: int = 60, fps: float = 10.0) -> Path:
    """Gera um .mp4 sintético com retângulos coloridos em movimento —
    válido para o OpenCV, não contém pessoas reais (MediaPipe não deteta ninguém).
    """
    destino = Path(destino)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(destino), fourcc, fps, (320, 240))
    for i in range(max(0, n_frames)):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        x = 100 + int(80 * np.sin(2 * np.pi * i / max(1, n_frames)))
        cv2.rectangle(frame, (x, 80), (x + 40, 160), (0, 0, 255), -1)
        out.write(frame)
    out.release()
    return destino


@pytest.fixture(autouse=True)
def _modo_local(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.chdir(tmp_path)  # evidência (output/) não polui o repo


# --------------------------------------------------------------------------- #
# Documento (unitário — PDF gerado)
# --------------------------------------------------------------------------- #
def test_documento_sem_anomalia_resume_sem_alerta(tmp_path):
    pdf = tmp_path / "presc.pdf"
    pdf.write_bytes(generate_prescription("p-1", "losartana", 50, "1x/dia", seed=1))

    r = analise._analisar_documento(pdf, prescricao_anterior=None)

    assert r.pontuacao == 0.0
    assert "Losartana" in r.resumo
    assert "sem alteração" in r.resumo.lower()


def test_documento_variacao_abrupta_vira_resumo_clinico(tmp_path):
    pdf = tmp_path / "presc.pdf"
    pdf.write_bytes(generate_prescription("p-1", "losartana", 100, "1x/dia", seed=2))
    anterior = PrescriptionRecord("p-1", "losartana", 50.0, "mg", "1x/dia", "2026-01-01T00:00:00")

    r = analise._analisar_documento(pdf, prescricao_anterior=anterior)

    assert r.pontuacao == 1.0
    assert "100%" in r.resumo  # variação relativa em linguagem clínica
    assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Vídeo (integração — sequência URFD real)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_video_sequencia_de_queda_real_produz_resumo_e_evidencia(tmp_path):
    seq = _REPO_ROOT / "data" / "urfd" / "fall-23"
    if not seq.is_dir():
        pytest.skip("dataset URFD ausente — rode `make data`")

    r = analise._analisar_video(seq, run_id="teste-video")

    assert 0.0 <= r.pontuacao <= 1.0
    assert r.resumo  # sempre há um resumo em linguagem clínica
    if r.pontuacao == 1.0:
        assert "queda" in r.resumo.lower()
        assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Vídeo (unitário — quadro cirúrgico único, ImageAnalyzer dublado)
# --------------------------------------------------------------------------- #
def _dublar_image_analyzer(monkeypatch, labels: list[ImageLabel]) -> None:
    monkeypatch.setattr(analise, "_pesos_yolo", lambda: Path("pesos-nao-usados.pt"))
    monkeypatch.setattr("pipelines.video.adapters.register_local_adapters", lambda pesos: None)
    monkeypatch.setattr(
        "aws.adapters.get_image_analyzer",
        lambda env=None: SimpleNamespace(
            analyze=lambda _bytes: ImageAnalysis(labels=labels, raw={})
        ),
    )


def test_video_quadro_unico_roteia_para_raia_cirurgica(monkeypatch, tmp_path):
    quadro = tmp_path / "quadro.jpg"
    quadro.write_bytes(b"conteudo-fake-do-quadro")
    _dublar_image_analyzer(monkeypatch, labels=[ImageLabel(name="tool", confidence=0.9)])

    r = analise._analisar_video(quadro, run_id="teste-objeto")

    assert r.detalhes.get("caso") == "cirurgico"
    assert r.pontuacao == 0.0  # "tool" não é estrutura crítica
    assert r.evidencia_id is None


def test_video_quadro_com_estrutura_critica_gera_evidencia_em_linguagem_clinica(
    monkeypatch, tmp_path
):
    quadro = tmp_path / "quadro.jpg"
    quadro.write_bytes(b"conteudo-fake-do-quadro")
    _dublar_image_analyzer(
        monkeypatch, labels=[ImageLabel(name="cystic_artery", confidence=0.87)]
    )

    r = analise._analisar_video(quadro, run_id="teste-objeto")

    assert r.pontuacao == 1.0
    assert "artéria cística" in r.resumo  # nome clínico, não o rótulo técnico
    assert "cystic_artery" not in r.resumo
    assert r.evidencia_id is not None


def test_video_diretorio_inexistente_e_arquivo_inexistente_falham_com_erro_claro(tmp_path):
    with pytest.raises(analise.ErroDeAnalise):
        analise._analisar_video(tmp_path / "nao-existe", run_id="teste-erro")


# --------------------------------------------------------------------------- #
# Vídeo (unitário — ficheiro .mp4, extração de frames + pipeline de pose)
# --------------------------------------------------------------------------- #
def test_extrair_frames_mp4_sintetico(tmp_path):
    video = _gerar_mp4_sintetico(tmp_path / "sintetico.mp4", n_frames=45)
    out = tmp_path / "frames"

    frames, fps = analise._extrair_frames(video, out)

    assert fps > 0
    assert len(frames) == 45
    assert all(p.suffix == ".png" for p in frames)
    assert all(p.is_file() for p in frames)
    # Ordem: os nomes são frame_000000.png, frame_000001.png, …
    assert frames == sorted(frames)


def test_extrair_frames_subamostra_videos_longos(tmp_path):
    video = _gerar_mp4_sintetico(tmp_path / "longo.mp4", n_frames=200, fps=30.0)
    out = tmp_path / "frames"

    frames = analise._extrair_frames(video, out, max_frames=50)

    assert 0 < len(frames) <= 50


def test_extrair_frames_mp4_corrompido_falha_com_erro_claro(tmp_path):
    fake = tmp_path / "falso.mp4"
    fake.write_bytes(b"isto nao e um video valido")

    with pytest.raises(analise.ErroDeAnalise, match="não foi possível abrir"):
        analise._extrair_frames(fake, tmp_path / "out")


def test_extrair_frames_video_inexistente_falha(tmp_path):
    with pytest.raises(analise.ErroDeAnalise, match="não encontrado"):
        analise._extrair_frames(tmp_path / "nao-ha.mp4", tmp_path / "out")


def test_video_mp4_roteia_para_pose_nao_para_cirurgico(tmp_path):
    """Regressão: um .mp4 não pode cair no ramo de quadro cirúrgico."""
    video = _gerar_mp4_sintetico(tmp_path / "movimento.mp4", n_frames=90)

    r = analise._analisar_video(video, run_id="teste-mp4")

    # Vídeo sintético não contém pessoa → sem queda, mas foi analisado como pose
    assert r.pontuacao == 0.0
    assert r.detalhes.get("formato") == "video"
    assert "alterações" in r.resumo.lower() or "queda" in r.resumo.lower()
    # Não foi para o ramo cirúrgico
    assert r.detalhes.get("caso") != "cirurgico"


def test_video_mp4_muito_curto_sem_janela_minima(tmp_path):
    """Vídeo com menos de 30 frames → curto demais para windowed_features."""
    video = _gerar_mp4_sintetico(tmp_path / "curto.mp4", n_frames=15)

    r = analise._analisar_video(video, run_id="teste-curto")

    assert r.pontuacao is None
    assert "curto" in r.resumo.lower()


def test_video_jpg_mantem_comportamento_cirurgico(monkeypatch, tmp_path):
    """Regressão: um .jpg continua a ser analisado como quadro cirúrgico."""
    quadro = tmp_path / "frame.jpg"
    quadro.write_bytes(b"falso-jpg")
    monkeypatch.setattr(analise, "_pesos_yolo", lambda: Path("p.pt"))
    monkeypatch.setattr("pipelines.video.adapters.register_local_adapters", lambda p: None)
    monkeypatch.setattr(
        "aws.adapters.get_image_analyzer",
        lambda env=None: SimpleNamespace(
            analyze=lambda _bytes: ImageAnalysis(
                labels=[ImageLabel(name="tool", confidence=0.9)], raw={}
            )
        ),
    )

    r = analise._analisar_video(quadro, run_id="teste-jpg")

    assert r.detalhes.get("caso") == "cirurgico"


def test_video_diretorio_mantem_comportamento_pose(tmp_path):
    """Regressão: um diretório com estrutura URFD chama _analisar_postura."""
    # Simula um diretório que o load_sequence tentaria ler — vai falhar
    # porque não tem estrutura URFD real, mas o dispatch (is_dir → pose)
    # é o que queremos confirmar.
    d = tmp_path / "fall-99"
    d.mkdir()

    # load_sequence vai lançar FileNotFoundError dentro de _analisar_postura
    # porque não existe o subdiretório *-cam0-rgb; isso é esperado.
    with pytest.raises((analise.ErroDeAnalise, FileNotFoundError)):
        analise._analisar_video(d, run_id="teste-dir")


# --------------------------------------------------------------------------- #
# Vídeo cirúrgico (unitário — .mp4 sintético + YOLOv8 dublado)
# --------------------------------------------------------------------------- #
def test_video_cirurgico_mp4_extrai_keyframes_e_roda_yolo(monkeypatch, tmp_path):
    """Um .mp4 com modalidade video_cirurgico extrai keyframes e analisa cada um."""
    video = _gerar_mp4_sintetico(tmp_path / "cirurgia.mp4", n_frames=90, fps=30.0)
    _dublar_image_analyzer(
        monkeypatch,
        labels=[ImageLabel(name="cystic_duct", confidence=0.92)],
    )

    r = analise._analisar_video_cirurgico(video, run_id="teste-cirurgico")

    assert r.pontuacao == 1.0
    assert "ducto cístico" in r.resumo
    assert r.detalhes.get("caso") == "cirurgico"
    assert r.detalhes.get("formato") == "video"
    assert r.evidencia_id is not None


def test_video_cirurgico_jpg_mantem_analise_de_quadro_unico(monkeypatch, tmp_path):
    """Regressão: um .jpg com modalidade video_cirurgico analisa como quadro único."""
    quadro = tmp_path / "frame.jpg"
    quadro.write_bytes(b"falso-jpg")
    _dublar_image_analyzer(
        monkeypatch,
        labels=[ImageLabel(name="cystic_artery", confidence=0.88)],
    )

    r = analise._analisar_video_cirurgico(quadro, run_id="teste-quadro")

    assert r.detalhes.get("caso") == "cirurgico"
    assert "artéria cística" in r.resumo


def test_video_cirurgico_sem_estruturas_criticas(monkeypatch, tmp_path):
    """Vídeo cirúrgico sem estruturas críticas → pontuação 0, sem evidência."""
    video = _gerar_mp4_sintetico(tmp_path / "vazio.mp4", n_frames=30)
    _dublar_image_analyzer(
        monkeypatch,
        labels=[ImageLabel(name="tool", confidence=0.5)],  # tool não é estrutura crítica
    )

    r = analise._analisar_video_cirurgico(video, run_id="teste-vazio")

    assert r.pontuacao == 0.0
    assert r.evidencia_id is None
    assert "Nenhuma estrutura crítica" in r.resumo


# --------------------------------------------------------------------------- #
# Sinais vitais (integração — registro CTU-UHB real)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_sinais_vitais_registro_real_produz_resumo(tmp_path):
    ctu = _REPO_ROOT / "data" / "ctu-uhb"
    if not ctu.is_dir():
        pytest.skip("dataset CTU-UHB ausente — rode `make data`")
    heas = sorted(ctu.glob("*.hea"))
    if not heas:
        pytest.skip("nenhum registro CTU-UHB encontrado")

    r = analise._analisar_sinais_vitais(heas[0], run_id="teste-vitais")

    assert r.resumo
    assert 0.0 <= r.pontuacao <= 1.0
    if r.pontuacao == 1.0:
        assert "frequência cardíaca" in r.resumo.lower()
        assert r.evidencia_id is not None


# --------------------------------------------------------------------------- #
# Áudio (integração — gravação ICBHI real; treina o classificador sob demanda)
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_sinais_vitais_roteia_bidmc_para_o_caso_de_internacao(tmp_path):
    bidmc = _REPO_ROOT / "data" / "bidmc"
    if not (bidmc / "bidmc32n.hea").is_file():
        pytest.skip("registro BIDMC ausente — rode `make data`")

    # o despacho reconhece o registro pelos canais (HR/SpO2) e roteia p/ internação
    r = analise._analisar_sinais_vitais(bidmc / "bidmc32n.hea", run_id="teste-internacao")

    assert r.detalhes.get("caso") == "internacao"
    assert r.resumo
    if r.pontuacao == 1.0:
        assert r.evidencia_id is not None


@pytest.mark.integration
def test_audio_gravacao_real_produz_resumo_respiratorio(tmp_path, monkeypatch):
    icbhi = _REPO_ROOT / "data" / "icbhi" / "ICBHI_final_database"
    if not icbhi.is_dir():
        pytest.skip("dataset ICBHI ausente — rode `make data`")
    wavs = sorted(icbhi.glob("*.wav"))
    if not wavs:
        pytest.skip("nenhuma gravação ICBHI encontrada")

    r = analise._analisar_audio(wavs[0], run_id="teste-audio", dataset_icbhi=icbhi, seed=42)

    assert r.resumo
    # pontuação é a confiança do classificador (0.0 quando não há alteração)
    assert r.pontuacao is None or 0.0 <= r.pontuacao <= 1.0


# --------------------------------------------------------------------------- #
# Áudio — dispatcher (unitário)
# --------------------------------------------------------------------------- #
def test_audio_sem_txt_roteia_para_consulta_nao_para_respiratorio(monkeypatch, tmp_path):
    """Áudio sem .txt ao lado → dispatcher chama _analisar_audio_consulta."""
    audio = tmp_path / "consulta.wav"
    audio.write_bytes(b"fake-audio-content")

    # Dubla a transcrição e as features acústicas para não carregar modelos reais
    monkeypatch.setattr(
        "pipelines.audio.transcribe.transcribe",
        lambda audio_path, model_size, no_speech_threshold, model=None: type(
            "Transcript",
            (),
            {
                "audio_path": audio_path,
                "text": "paciente relata dor no peito",
                "segments": [],
                "reliable": True,
            },
        )(),
    )
    monkeypatch.setattr(
        "pipelines.audio.acoustic_features.extract",
        lambda audio_path, transcript: type(
            "AcousticFeatures",
            (),
            {
                "jitter_local": 0.003,
                "shimmer_local": 0.018,
                "hnr_db": 19.6,
                "pause_rate": 0.1,
                "speaking_rate_wps": 3.5,
            },
        )(),
    )
    # Dubla o detector de padrão respiratório (evita ler o ficheiro fake com soundfile)
    monkeypatch.setattr(
        "pipelines.audio.respiratory_pattern.detect_respiratory_pattern",
        lambda audio_path, sr=22050, frame_ms=30.0: {
            "detected": False,
            "breath_rate_bpm": None,
            "confidence": 0.0,
            "method": "mock",
        },
    )

    r = analise._analisar_audio(audio, run_id="teste-consulta", dataset_icbhi=tmp_path, seed=42)

    assert r.resumo
    assert r.pontuacao is not None
    assert "dor no peito" in r.resumo.lower()
    assert r.detalhes.get("termos_criticos_encontrados", 0) >= 1
    # AUDIO-01: evidência consolidada com campos do novo contrato
    assert r.evidencia_id is not None
    assert "consulta" in r.evidencia_id
    # verifica que o sidecar JSON foi escrito
    import json
    sidecar = tmp_path / "output" / "audio" / "teste-consulta" / f"{r.evidencia_id}.json"
    assert sidecar.is_file(), f"sidecar não encontrado: {sidecar}"
    payload = json.loads(sidecar.read_text())
    assert payload["modality"] == "audio"
    assert payload["severity"] in ("MEDIUM", "HIGH")
    assert payload["status"] == "positive"
    assert len(payload["metadata"]["termos_criticos"]) >= 1


# --------------------------------------------------------------------------- #
# Contexto de cena via Rekognition (complemento à pipeline de postura)
# --------------------------------------------------------------------------- #

def _dublar_contexto_cena_aws(monkeypatch, labels: list[ImageLabel]) -> None:
    """Configura o ambiente para simular ``ENV=aws`` com labels de cena dubladas.

    Regista o adaptador cloud como no-op e dubla ``get_image_analyzer`` para
    devolver as labels fornecidas, sem chamar o Rekognition real.
    """
    monkeypatch.setenv("ENV", "aws")
    monkeypatch.setattr("aws.adapters.cloud.register_cloud_adapters", lambda: None)
    monkeypatch.setattr(
        "aws.adapters.get_image_analyzer",
        lambda env=None: SimpleNamespace(
            analyze=lambda _bytes: ImageAnalysis(
                labels=labels,
                raw={"Labels": [{"Name": l.name, "Categories": []} for l in labels]},
            )
        ),
    )


class TestContextoCenaHelper:
    """Testes unitários para ``_analisar_contexto_cena``."""

    def test_env_local_retorna_none(self):
        """Com ENV=local, a função retorna None sem chamar a cloud."""
        resultado = analise._analisar_contexto_cena(b"\xff\xd8\xff\xe0")  # JPEG header mínimo
        assert resultado is None

    def test_env_aws_sem_labels_relevantes_retorna_none(self, monkeypatch):
        """Labels que não estão no mapa clínico → retorna None."""
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[ImageLabel(name="Car", confidence=0.95)],
        )
        resultado = analise._analisar_contexto_cena(b"fake-frame")
        assert resultado is None

    def test_env_aws_com_labels_clinicas_retorna_contexto(self, monkeypatch):
        """Labels no mapa clínico → retorna dict com objetos, pessoas, ambiente."""
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[
                ImageLabel(name="Hospital", confidence=0.99),
                ImageLabel(name="Bed", confidence=0.95),
                ImageLabel(name="Wheelchair", confidence=0.88),
                ImageLabel(name="Nurse", confidence=0.92),
                ImageLabel(name="Standing", confidence=0.85),
            ],
        )
        resultado = analise._analisar_contexto_cena(b"fake-frame")
        assert resultado is not None
        assert resultado["ambiente"] == "Hospital"
        assert any(o["nome"] == "Cadeira de Rodas" for o in resultado["objetos"])
        assert any(o["nome"] == "Cama" for o in resultado["objetos"])
        assert "Enfermeiro" in resultado["pessoas"]
        assert resultado["acao"] == "Em Pé"

    def test_confianca_abaixo_do_threshold_e_filtrada(self, monkeypatch):
        """Labels com confiança < 70% são ignoradas."""
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[
                ImageLabel(name="Wheelchair", confidence=0.65),  # abaixo do threshold
                ImageLabel(name="Bed", confidence=0.69),          # abaixo do threshold
                ImageLabel(name="Hospital", confidence=0.71),     # acima
            ],
        )
        resultado = analise._analisar_contexto_cena(b"fake-frame")
        assert resultado is not None
        assert resultado["ambiente"] == "Hospital"
        # Nenhum objeto porque Wheelchair e Bed foram filtrados
        assert len(resultado["objetos"]) == 0

    def test_falha_no_rekognition_retorna_none(self, monkeypatch):
        """Se o analisador lançar exceção, retorna None sem propagar."""
        monkeypatch.setenv("ENV", "aws")
        monkeypatch.setattr("aws.adapters.cloud.register_cloud_adapters", lambda: None)
        monkeypatch.setattr(
            "aws.adapters.get_image_analyzer",
            lambda env=None: SimpleNamespace(
                analyze=lambda _bytes: (_ for _ in ()).throw(
                    Exception("Rekognition timeout")
                )
            ),
        )
        resultado = analise._analisar_contexto_cena(b"fake-frame")
        assert resultado is None

    def test_medical_category_fallback(self, monkeypatch):
        """Labels com categoria 'Medical' no raw são incluídas mesmo sem nome exato."""
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[ImageLabel(name="IVPole", confidence=0.85)],
        )
        # Sobrescreve o raw para incluir a categoria Medical
        monkeypatch.setattr(
            "aws.adapters.get_image_analyzer",
            lambda env=None: SimpleNamespace(
                analyze=lambda _bytes: ImageAnalysis(
                    labels=[ImageLabel(name="IVPole", confidence=0.85)],
                    raw={
                        "Labels": [
                            {
                                "Name": "IVPole",
                                "Categories": [{"Name": "Medical"}],
                            }
                        ]
                    },
                )
            ),
        )
        resultado = analise._analisar_contexto_cena(b"fake-frame")
        assert resultado is not None
        # IVPole não está no mapa, mas categoria Medical → incluído
        assert any(o["nome"] == "IVPole" for o in resultado["objetos"])


class TestContextoCenaVideoPose:
    """Testes de integração: contexto de cena enriquece o ResultadoAnalise."""

    def test_mp4_sem_contexto_nao_tem_chave_no_detalhes(self, monkeypatch, tmp_path):
        """Sem labels clínicas → ``contexto_cena`` não aparece nos detalhes."""
        video = _gerar_mp4_sintetico(tmp_path / "sem_contexto.mp4", n_frames=60)
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[ImageLabel(name="Car", confidence=0.95)],  # irrelevante
        )

        r = analise._analisar_video_pose(video, run_id="teste-sem-ctx")

        assert "contexto_cena" not in r.detalhes
        assert r.pontuacao == 0.0  # vídeo sintético sem pessoa

    def test_mp4_com_contexto_enriquece_detalhes(self, monkeypatch, tmp_path):
        """Labels clínicas → ``contexto_cena`` aparece nos detalhes."""
        video = _gerar_mp4_sintetico(tmp_path / "com_contexto.mp4", n_frames=60)
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[
                ImageLabel(name="Hospital", confidence=0.99),
                ImageLabel(name="Bed", confidence=0.95),
                ImageLabel(name="Wheelchair", confidence=0.88),
            ],
        )

        r = analise._analisar_video_pose(video, run_id="teste-com-ctx")

        assert "contexto_cena" in r.detalhes
        ctx = r.detalhes["contexto_cena"]
        assert ctx["ambiente"] == "Hospital"
        assert any(o["nome"] == "Cadeira de Rodas" for o in ctx["objetos"])
        assert any(o["nome"] == "Cama" for o in ctx["objetos"])

    def test_mp4_com_contexto_enriquece_resumo(self, monkeypatch, tmp_path):
        """O resumo 'Sem alterações' é enriquecido com o ambiente."""
        video = _gerar_mp4_sintetico(tmp_path / "ctx_resumo.mp4", n_frames=60)
        _dublar_contexto_cena_aws(
            monkeypatch,
            labels=[
                ImageLabel(name="Bed", confidence=0.95),
                ImageLabel(name="Wheelchair", confidence=0.85),
                ImageLabel(name="Standing", confidence=0.80),
            ],
        )

        r = analise._analisar_video_pose(video, run_id="teste-ctx-resumo")

        assert "Ambiente:" in r.resumo
        assert "Cadeira de Rodas" in r.resumo
        assert "Cama" in r.resumo

    def test_mp4_com_falha_no_rekognition_continua_normal(self, monkeypatch, tmp_path):
        """Falha no Rekognition → pipeline de pose continua sem contexto."""
        video = _gerar_mp4_sintetico(tmp_path / "falha_aws.mp4", n_frames=60)
        monkeypatch.setenv("ENV", "aws")
        monkeypatch.setattr("aws.adapters.cloud.register_cloud_adapters", lambda: None)
        monkeypatch.setattr(
            "aws.adapters.get_image_analyzer",
            lambda env=None: SimpleNamespace(
                analyze=lambda _bytes: (_ for _ in ()).throw(
                    ConnectionError("Rekognition unreachable")
                )
            ),
        )

        r = analise._analisar_video_pose(video, run_id="teste-falha-aws")

        # Pipeline concluiu normalmente
        assert r.pontuacao == 0.0
        assert "contexto_cena" not in r.detalhes
        # Sem "Ambiente:" no resumo porque o contexto falhou
        assert "Ambiente:" not in r.resumo

def test_audio_com_txt_roteia_para_respiratorio(monkeypatch, tmp_path):
    """Áudio com .txt ao lado → dispatcher chama _analisar_audio_respiratorio.

    Como não há dataset ICBHI neste teste unitário, a carga do dataset falha —
    mas o importante é que o dispatcher NÃO lança ErroDeAnalise por falta
    de .txt (ele encontrou o .txt, logo roteou para o ramo respiratório).
    """
    # Nome com formato ICBHI: 5 campos separados por underscore
    audio = tmp_path / "101_1b1_Al_sc_Meditron.wav"
    audio.write_bytes(b"fake-audio-content")
    anotacao = tmp_path / "101_1b1_Al_sc_Meditron.txt"
    anotacao.write_text("0.0\t1.0\t0\t0\n", encoding="utf-8")

    # O ramo respiratório vai tentar carregar o dataset ICBHI — não existe aqui,
    # então esperamos FileNotFoundError (do load_dataset), não ErroDeAnalise.
    with pytest.raises(FileNotFoundError):
        inexistente = tmp_path / "inexistente"
        analise._analisar_audio(audio, run_id="teste-resp", dataset_icbhi=inexistente, seed=42)
