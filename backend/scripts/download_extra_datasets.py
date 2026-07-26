"""Baixa, de forma idempotente, os conjuntos de dados extras usados pelo sistema.

Cada dataset vive num subdiretório de ``data/`` e é protegido por um arquivo
sentinela ``.complete`` — mesmo mecanismo do script shell ``download_datasets.sh``
para os datasets principais. A falha de um dataset não interrompe os demais.

Uso::

    PYTHONPATH=backend python -m scripts.download_extra_datasets
    # ou
    make data-extra

Datasets cobertos:
- Common Voice PT-BR (áudio em português, transcrição)
- Laryngeal Voice Disorder (voz patológica, fadiga vocal)
- UI-PRMD Skeleton (fisioterapia, desvio angular)
- KIMORE JSON (fisioterapia, pacientes reais)
- m2cai16-tool-locations (detecção de instrumentos cirúrgicos)
- SemClinBr (texto clínico pt-BR, termos/sentimento — documentado, não baixado)
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

logger = logging.getLogger("data-extra")

# ── sentinelas (mesmo contrato do download_datasets.sh) ──────────────
def _is_complete(dest: Path) -> bool:
    return (dest / ".complete").exists()


def _mark_complete(dest: Path) -> None:
    (dest / ".complete").touch()


# ── helpers ──────────────────────────────────────────────────────────
def _check_disk_space(data_dir: Path, need_bytes: int) -> bool:
    usage = shutil.disk_usage(data_dir)
    if usage.free < need_bytes:
        logger.error(
            "Espaço insuficiente em %s: precisa de %d bytes, há %d",
            data_dir, need_bytes, usage.free,
        )
        return False
    return True


def _run_fetch(name: str, fn, results: dict) -> None:
    """Executa um fetch sem deixar a falha derrubar os demais."""
    try:
        status = fn()
        results[name] = status
    except Exception:
        logger.exception("%s: exceção inesperada", name)
        results[name] = "falhou"


def _fetch_zip(url: str, dest_dir: Path, label: str) -> str:
    """Baixa um zip com retomada, extrai e retorna 'baixado' ou 'pulado'.

    Usa ``curl -C -`` para retomada (mesmo padrão do shell script).
    """
    if _is_complete(dest_dir):
        logger.info("%s: já completo — pulando", label)
        return "pulado"

    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / f"{label.lower().replace(' ', '-')}.zip"

    logger.info("%s: baixando com retomada", label)
    rc = subprocess.run(
        ["curl", "-sS", "-L", "-C", "-", "-o", str(zip_path), url],
        check=False,
    )
    if rc.returncode != 0:
        logger.error("%s: download falhou (curl rc=%d)", label, rc.returncode)
        zip_path.unlink(missing_ok=True)
        return "falhou"

    # Verificar que é um zip real (mesma lógica verify_zip do shell)
    if zip_path.stat().st_size < 1000:
        logger.error("%s: arquivo pequeno demais — não é um zip", label)
        zip_path.unlink(missing_ok=True)
        return "falhou"
    with open(zip_path, "rb") as fh:
        if fh.read(4) != b"PK\x03\x04":
            logger.error("%s: assinatura zip inválida — possível página de erro", label)
            zip_path.unlink(missing_ok=True)
            return "falhou"

    logger.info("%s: extraindo", label)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        logger.error("%s: extração falhou — zip corrompido", label)
        zip_path.unlink(missing_ok=True)
        return "falhou"

    zip_path.unlink(missing_ok=True)  # limpa o zip após extração
    _mark_complete(dest_dir)
    logger.info("%s: OK", label)
    return "baixado"


# ── fetch functions ──────────────────────────────────────────────────

def fetch_common_voice_ptbr(data_dir: Path) -> str:
    """Common Voice PT-BR — amostras de fala real em português.

    O dataset do Hugging Face (mozilla-foundation/common_voice_*) migrou para
    Parquet e as versões antigas (baseadas em loading script) estão quebradas
    na biblioteca ``datasets`` ≥ 5.0. A abordagem atual é baixar diretamente do
    CDN da Mozilla (S3 público).

    O TTS de consulta (``make tts-consulta``) já gera áudio sintético em pt-BR
    que exercita o pipeline de transcrição. Este dataset complementa com voz
    humana real — mas não é bloqueador para a demonstração.
    """
    dest = data_dir / "common-voice-ptbr"
    if _is_complete(dest):
        logger.info("Common Voice PT-BR: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)

    # CDN público da Mozilla — versão 17.0 em português.
    base_url = (
        "https://mozilla-common-voice-datasets.s3.us-west-2.amazonaws.com"
        "/cv-corpus-17.0"
    )
    tar_name = "cv-corpus-17.0-2024-03-15-pt.tar.gz"
    tar_url = f"{base_url}/{tar_name}"

    logger.info("Common Voice PT-BR: baixando validated.tsv do CDN da Mozilla")
    logger.info("  (extraindo apenas o TSV do tar.gz — o download é grande mas")
    logger.info("   só o cabeçalho é salvo; pode levar alguns minutos)")

    # Baixar o tar.gz com pipe pelo tar para extrair só o validated.tsv.
    # O `head -21` pega o cabeçalho + 20 linhas de dados e corta o pipe,
    # então o curl para de baixar assim que o tar termina.
    tsv_path = dest / "validated.tsv"
    curl_cmd = (
        f"curl -sSL '{tar_url}' "
        f"| tar xz --to-stdout --wildcards '*/validated.tsv' 2>/dev/null "
        f"| head -21 > '{tsv_path}'"
    )
    rc = subprocess.run(["bash", "-c", curl_cmd], check=False)
    if rc.returncode != 0 or not tsv_path.exists() or tsv_path.stat().st_size < 100:
        logger.warning("Common Voice PT-BR: download do TSV falhou — criando instruções manuais")
        tsv_path.unlink(missing_ok=True)
        _escrever_instrucoes_common_voice(dest)
        return "documentado"

    # Extrair os nomes dos clipes do TSV
    clips: list[str] = []
    with open(tsv_path, encoding="utf-8") as fh:
        fh.readline()  # header
        for line in fh:
            parts = line.strip().split("\t")
            if parts:
                # Primeira coluna é o caminho do clipe
                clip_name = parts[0].strip()
                if clip_name:
                    clips.append(clip_name)

    if not clips:
        logger.warning("Common Voice PT-BR: TSV sem clipes — criando instruções manuais")
        _escrever_instrucoes_common_voice(dest)
        return "documentado"

    # Baixar os primeiros 20 clipes individuais do CDN
    logger.info("Common Voice PT-BR: baixando %d clipes individuais", min(20, len(clips)))
    saved = 0
    for clip_name in clips[:20]:
        clip_url = f"{base_url}/clips/{clip_name}"
        out = dest / clip_name
        rc = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", "30", "-o", str(out), clip_url],
            check=False,
        )
        if rc.returncode == 0 and out.stat().st_size > 1000:
            saved += 1
        else:
            out.unlink(missing_ok=True)

    if saved == 0:
        logger.warning("Common Voice PT-BR: nenhum clipe baixado — criando instruções manuais")
        _escrever_instrucoes_common_voice(dest)
        return "documentado"

    _mark_complete(dest)
    logger.info("Common Voice PT-BR: OK (%d clipes)", saved)
    return "baixado"


def _escrever_instrucoes_common_voice(dest: Path) -> None:
    """Escreve instruções para baixar o Common Voice manualmente."""
    instrucoes = dest / "COMO_BAIXAR.md"
    instrucoes.write_text(
        "# Common Voice PT-BR — instruções para baixar manualmente\n\n"
        "O download automático não conseguiu aceder ao CDN da Mozilla.\n\n"
        "Para baixar manualmente:\n\n"
        "1. Acesse https://commonvoice.mozilla.org/pt/datasets\n"
        "2. Escolha a versão mais recente com português\n"
        "3. Baixe o arquivo tar.gz e extraia a pasta `clips/` + `validated.tsv`\n"
        "4. Coloque os arquivos neste diretório:\n"
        f"   {dest}/\n"
        "5. Crie o arquivo `.complete`:\n"
        f"   touch {dest / '.complete'}\n\n"
        "Alternativa: o `make tts-consulta` já gera áudio sintético em pt-BR\n"
        "que cobre a validação de transcrição para a demonstração.\n",
        encoding="utf-8",
    )


def fetch_laryngeal_voice(data_dir: Path) -> str:
    """Laryngeal Voice Disorder — vozes saudáveis e patológicas (Kaggle)."""
    dest = data_dir / "laryngeal"
    if _is_complete(dest):
        logger.info("Laryngeal Voice: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("Laryngeal Voice: baixando via Kaggle Hub")

    try:
        import kagglehub
    except ImportError:
        logger.error("Laryngeal Voice: biblioteca 'kagglehub' não instalada")
        return "falhou"

    try:
        cached = kagglehub.dataset_download(
            "sree14hari/svd-dataset",
            output_dir=str(dest),
        )
        logger.info("Laryngeal Voice: cache em %s", cached)
    except Exception:
        logger.exception("Laryngeal Voice: falha no download")
        return "falhou"

    # kagglehub coloca os arquivos no diretório de output, mas pode criar
    # subdiretórios com versão. Copiar tudo para dest/ raiz se necessário.
    wavs = list(dest.rglob("*.wav"))
    if not wavs:
        logger.error("Laryngeal Voice: nenhum WAV encontrado após download")
        return "falhou"

    _mark_complete(dest)
    logger.info("Laryngeal Voice: OK (%d arquivos WAV)", len(wavs))
    return "baixado"


def fetch_ui_prmd(data_dir: Path) -> str:
    """UI-PRMD Skeleton — dados de esqueleto de fisioterapia (GitHub mirror).

    O site oficial (webpages.uidaho.edu/ui-prmd) está fora do ar. Usamos o
    mirror do repositório avakanski que contém CSVs de ângulos/esqueleto pré-
    processados para o exercício de agachamento (deep squat), nos formatos
    correto e incorreto.
    """
    dest = data_dir / "ui-prmd"
    if _is_complete(dest):
        logger.info("UI-PRMD: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("UI-PRMD: baixando CSVs de esqueleto do GitHub (avakanski)")

    base = "https://raw.githubusercontent.com/avakanski/A-Deep-Learning-Framework-for-Assessing-Physical-Rehabilitation-Exercises/master/Data"
    files = [
        "Data_Correct.csv",
        "Data_Incorrect.csv",
        "Labels_Correct.csv",
        "Labels_Incorrect.csv",
    ]

    saved = 0
    for fname in files:
        url = f"{base}/{fname}"
        out = dest / fname
        rc = subprocess.run(
            ["curl", "-sS", "-L", "-o", str(out), url],
            check=False,
        )
        if rc.returncode == 0 and out.stat().st_size > 100:
            saved += 1
        else:
            logger.warning("UI-PRMD: falha ao baixar %s", fname)
            out.unlink(missing_ok=True)

    if saved == 0:
        logger.error("UI-PRMD: nenhum arquivo baixado")
        return "falhou"

    _mark_complete(dest)
    logger.info("UI-PRMD: OK (%d arquivos)", saved)
    return "baixado"


def fetch_kimore(data_dir: Path) -> str:
    """KIMORE — esqueleto 3D de fisioterapia com pacientes reais.

    O dataset original está num Google Drive (link do artigo IEEE TNSRE 2019).
    O wrapper ``petteriTeikari/KiMoRe_wrapper`` converte JSON → HDF5/MAT mas
    não redistribui os dados. Este fetch clona o wrapper e documenta o caminho
    para obter os dados originais.
    """
    dest = data_dir / "kimore"
    if _is_complete(dest):
        logger.info("KIMORE: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("KIMORE: clonando wrapper (petteriTeikari/KiMoRe_wrapper)")

    rc = subprocess.run(
        [
            "git", "clone", "--depth", "1",
            "https://github.com/petteriTeikari/KiMoRe_wrapper.git",
            str(dest / "wrapper"),
        ],
        check=False,
    )
    if rc.returncode != 0:
        logger.error("KIMORE: clone do wrapper falhou")
        return "falhou"

    # Escrever instruções para obter os dados originais
    instrucoes = dest / "COMO_BAIXAR_DADOS.md"
    instrucoes.write_text(
        "# KIMORE — instruções para baixar os dados originais\n\n"
        "O wrapper foi clonado em `wrapper/`. Os dados originais (JSON de\n"
        "esqueleto Kinect) estão no Google Drive do artigo:\n\n"
        "https://drive.google.com/drive/folders/1b1anGzSytePiCUyoz8AlGMV2G54e_ZeC\n\n"
        "Baixe a pasta `Kimore/` do Google Drive e coloque-a AQUI (ao lado\n"
        "do wrapper), seguindo a estrutura esperada pelo wrapper:\n\n"
        "  data/kimore/Kimore/  → os JSONs de esqueleto\n"
        "  data/kimore/wrapper/ → o conversor MATLAB/R\n\n"
        "Depois de colocar os dados, crie o arquivo `.complete` manualmente:\n"
        "  touch data/kimore/.complete\n",
        encoding="utf-8",
    )

    logger.warning(
        "KIMORE: wrapper clonado, mas os dados originais precisam ser "
        "baixados manualmente do Google Drive — veja %s",
        instrucoes,
    )
    return "baixado"


def fetch_m2cai16(data_dir: Path) -> str:
    """m2cai16-tool-locations — detecção de instrumentos cirúrgicos.

    O dataset original de Stanford (Jin et al., WACV 2018) é um zip de ~145 MB
    com 2.532 frames anotados e 7 classes de instrumentos. O servidor de
    Stanford é muito lento (~1 KB/s) para download automatizado.

    A alternativa mais rápida é o Roboflow Universe, que já entrega no formato
    YOLOv8 (sem conversão)::

        from roboflow import Roboflow
        rf = Roboflow(api_key="SUA_KEY")
        ds = rf.workspace("camma").project("m2cai16-tool-locations")
        ds.version(1).download("yolov8", location="data/m2cai16")

    Também é possível baixar o zip de Stanford manualmente pelo navegador
    (costuma ser mais rápido que curl/wget daqui).
    """
    dest = data_dir / "m2cai16"
    if _is_complete(dest):
        logger.info("m2cai16: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)

    url = "http://ai.stanford.edu/~syyeung/resources/m2cai16-tool-locations.zip"
    logger.info("m2cai16: tentando Stanford (timeout 5 min, servidor lento)")

    # Tentar com curl e timeout de 5 minutos. Se o servidor for muito lento,
    # abortar e documentar as alternativas.
    zip_path = dest / "m2cai16-tool-locations.zip"
    rc = subprocess.run(
        [
            "curl", "-sS", "-L", "--max-time", "300",
            "-o", str(zip_path), url,
        ],
        check=False,
    )
    if rc.returncode != 0:
        logger.warning("m2cai16: download falhou/timeout — documentando alternativas")
        zip_path.unlink(missing_ok=True)
        _escrever_instrucoes_m2cai16(dest)
        return "documentado"

    if not _verify_zip(zip_path):
        logger.warning("m2cai16: zip inválido — documentando alternativas")
        zip_path.unlink(missing_ok=True)
        _escrever_instrucoes_m2cai16(dest)
        return "documentado"

    # Extrair
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
    except zipfile.BadZipFile:
        logger.warning("m2cai16: extração falhou — documentando alternativas")
        zip_path.unlink(missing_ok=True)
        _escrever_instrucoes_m2cai16(dest)
        return "documentado"

    zip_path.unlink(missing_ok=True)
    _mark_complete(dest)
    logger.info("m2cai16: OK")
    return "baixado"


def _verify_zip(path: Path) -> bool:
    """Verifica que o arquivo é um zip válido (mesma lógica do shell script)."""
    if not path.exists() or path.stat().st_size < 1000:
        return False
    with open(path, "rb") as fh:
        return fh.read(4) == b"PK\x03\x04"


def _escrever_instrucoes_m2cai16(dest: Path) -> None:
    """Escreve instruções para baixar o m2cai16 manualmente."""
    (dest / "COMO_BAIXAR.md").write_text(
        "# m2cai16-tool-locations — instruções para baixar\n\n"
        "O servidor de Stanford é muito lento para download automatizado.\n\n"
        "## Opção 1 — Roboflow (recomendado, já em YOLOv8)\n\n"
        "```python\n"
        "from roboflow import Roboflow\n"
        "rf = Roboflow(api_key=\"SUA_KEY\")\n"
        "ds = rf.workspace(\"camma\").project(\"m2cai16-tool-locations\")\n"
        "ds.version(1).download(\"yolov8\", location=\"data/m2cai16\")\n"
        "```\n\n"
        "## Opção 2 — Download direto de Stanford\n\n"
        "URL: http://ai.stanford.edu/~syyeung/resources/m2cai16-tool-locations.zip\n"
        "Tamanho: ~145 MB. Funciona no navegador.\n\n"
        "Depois de baixar, extraia o zip neste diretório e crie o `.complete`:\n\n"
        f"  touch {dest / '.complete'}\n",
        encoding="utf-8",
    )


def fetch_semclinbr(data_dir: Path) -> str:
    """SemClinBr — notas clínicas anotadas em português brasileiro.

    Dataset acadêmico (Journal of Biomedical Semantics, 2022): 1.000 notas
    clínicas com 65.117 entidades anotadas. Requer solicitação aos autores —
    não é baixado automaticamente.

    Referência: https://jbiomedsem.biomedcentral.com/articles/10.1186/s13326-022-00269-1
    """
    dest = data_dir / "semclinbr"
    if _is_complete(dest):
        logger.info("SemClinBr: já completo — pulando")
        return "pulado"

    dest.mkdir(parents=True, exist_ok=True)
    instrucoes = dest / "COMO_OBTER.md"
    instrucoes.write_text(
        "# SemClinBr — Corpus Clínico Semântico em Português Brasileiro\n\n"
        "Referência completa:\n"
        "  Oliveira et al., 'SemClinBr: a multi-institutional and multi-\n"
        "  specialty semantically annotated corpus for Portuguese clinical\n"
        "  NLP tasks', Journal of Biomedical Semantics, 2022.\n"
        "  https://jbiomedsem.biomedcentral.com/articles/10.1186/s13326-022-00269-1\n\n"
        "O dataset contém 1.000 notas clínicas reais em pt-BR, anotadas com\n"
        "65.117 entidades (sintomas, diagnósticos, tratamentos, exames) e\n"
        "11.263 relações. É o corpus de referência para validação de termos\n"
        "críticos e sentimento em vocabulário clínico real.\n\n"
        "Para obter acesso, entre em contato com os autores pelo artigo.\n"
        "Depois de obter os arquivos, coloque-os neste diretório e crie o\n"
        "arquivo `.complete`:\n"
        "  touch data/semclinbr/.complete\n",
        encoding="utf-8",
    )
    logger.warning("SemClinBr: requer solicitação aos autores — veja %s", instrucoes)
    return "documentado"


# ── main ─────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baixa datasets extras")
    parser.add_argument(
        "--data-dir", default="data",
        help="Diretório raiz dos datasets (default: data/)",
    )
    parser.add_argument(
        "--skip", nargs="*", default=[],
        choices=["common-voice", "laryngeal", "ui-prmd", "kimore", "m2cai16", "semclinbr"],
        help="Datasets a pular",
    )
    parser.add_argument(
        "--only", nargs="*", default=[],
        choices=["common-voice", "laryngeal", "ui-prmd", "kimore", "m2cai16", "semclinbr"],
        help="Baixar apenas estes datasets",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="[data-extra] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    data_dir = Path(args.data_dir).resolve()

    # Todos os fetchs registrados: (chave, label, função)
    registry: list[tuple[str, str, object]] = [
        ("common-voice", "Common Voice PT-BR", lambda: fetch_common_voice_ptbr(data_dir)),
        ("laryngeal", "Laryngeal Voice Disorder", lambda: fetch_laryngeal_voice(data_dir)),
        ("ui-prmd", "UI-PRMD Skeleton", lambda: fetch_ui_prmd(data_dir)),
        ("kimore", "KIMORE", lambda: fetch_kimore(data_dir)),
        ("m2cai16", "m2cai16-tool-locations", lambda: fetch_m2cai16(data_dir)),
        ("semclinbr", "SemClinBr", lambda: fetch_semclinbr(data_dir)),
    ]

    skip = set(args.skip)
    only = set(args.only)

    results: dict[str, str] = {}
    for key, label, fn in registry:
        if skip and key in skip:
            logger.info("%s: pulado (--skip)", label)
            results[label] = "pulado"
            continue
        if only and key not in only:
            continue
        logger.info("── %s ──", label)
        _run_fetch(label, fn, results)

    # Resumo
    ok = sum(1 for v in results.values() if v in ("baixado", "pulado", "documentado"))
    falhas = sum(1 for v in results.values() if v == "falhou")
    logger.info("── resumo ──")
    for label, status in results.items():
        logger.info("  %s: %s", label, status)
    logger.info("Total: %d ok, %d falhas", ok, falhas)

    return 1 if falhas > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
