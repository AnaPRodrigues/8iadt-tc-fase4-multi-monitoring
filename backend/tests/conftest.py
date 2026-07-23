"""Fixtures WFDB sintéticas — permitem testar sem baixar os GB do CTU-UHB.

O formato replica o real verificado: 4 Hz, sinais FHR e UC, pH em comentário.
Fica na raiz de ``tests/`` para servir tanto os testes unitários quanto os de integração.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import numpy as np
import pytest
import wfdb

from aws import adapters


@pytest.fixture(autouse=True)
def _registro_de_adapters_limpo(monkeypatch):
    """Isola o registro de adapters AWS entre testes (evita vazamento de estado global)."""
    monkeypatch.setattr(adapters, "_TEXT_EXTRACTORS", {})
    monkeypatch.setattr(adapters, "_IMAGE_ANALYZERS", {})

FS = 4

# ---- Harness do script shell de aquisição (F0) — sem download real ----
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "backend" / "scripts" / "download_datasets.sh"
_BASH = shutil.which("bash") or "/bin/bash"


def _mkexec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def stubbin(tmp_path):
    """Diretório de PATH com as ferramentas pedidas como stubs executáveis."""
    d = tmp_path / "bin"
    d.mkdir()

    def make(tools, bodies=None):
        bodies = bodies or {}
        for t in tools:
            _mkexec(d / t, bodies.get(t, "#!/usr/bin/env bash\nexit 0\n"))
        return d

    return make


@pytest.fixture
def run():
    """Roda `source script; <func_call>` e devolve o CompletedProcess.

    `path` substitui o PATH do filho (simula ferramentas presentes/ausentes);
    `cwd` default é a raiz do repo para resolver `.venv`.
    """

    def _run(func_call, path=None, env=None, cwd=_REPO_ROOT):
        full = os.environ.copy()
        if env:
            full.update(env)
        if path is not None:
            full["PATH"] = str(path)
        return subprocess.run(
            [_BASH, "-c", f"source '{_SCRIPT}'; {func_call}"],
            capture_output=True,
            text=True,
            env=full,
            cwd=str(cwd),
        )

    return _run


def escreve_registro(
    directory,
    record_name: str,
    *,
    ph: float | None = 7.26,
    n_amostras: int = 240,
    sig_name: tuple[str, ...] = ("FHR", "UC"),
    fhr_base: float = 140.0,
    uc_base: float = 20.0,
    fs: int = FS,
) -> str:
    """Escreve um par .hea/.dat válido e devolve o caminho sem extensão."""
    rng = np.random.default_rng(0)
    n_sig = len(sig_name)
    colunas = [rng.normal(fhr_base, 5.0, n_amostras)]
    colunas += [rng.normal(uc_base, 2.0, n_amostras) for _ in range(n_sig - 1)]
    sinal = np.column_stack(colunas).astype(float)

    comments = ["-- Outcome measures"]
    if ph is not None:
        comments.append(f"pH           {ph}")
    comments.append("Apgar1       8")

    wfdb.wrsamp(
        record_name,
        fs=fs,
        units=["bpm", "nd"][:n_sig],
        sig_name=list(sig_name),
        p_signal=sinal,
        fmt=["16"] * n_sig,
        comments=comments,
        write_dir=str(directory),
    )
    return str(directory / record_name)


@pytest.fixture
def escritor():
    """Devolve a função de escrita para testes que montam seus próprios lotes."""
    return escreve_registro


@pytest.fixture
def registro_valido(tmp_path):
    return escreve_registro(tmp_path, "0001", ph=7.26)


@pytest.fixture
def registro_patologico(tmp_path):
    return escreve_registro(tmp_path, "0002", ph=7.01)


# ---- Pesos reais de um detector de objetos (compartilhados entre os testes de detecção) ----
#
# O treino de produção desse detector vive inteiramente em `training/`, fora do
# backend (o backend só faz inferência). Esta função é infraestrutura de teste,
# não o treino do sistema: ela existe só para dar aos testes de inferência um
# modelo de verdade e rápido de treinar, sem depender de `training/` (que, por
# sua vez, também não pode depender do backend — nenhum dos dois lados importa
# o outro). Por isso ela duplica, de forma mínima e deliberada, os mesmos
# passos de conversão/treino que `training/finetune.py` faz de verdade.
_ENDOSCAPES_TRAIN = _REPO_ROOT / "data" / "endoscapes" / "endoscapes" / "train"
_ENDOSCAPES_COCO_JSON = _ENDOSCAPES_TRAIN / "annotation_coco.json"
_YOLO_BASE_WEIGHTS_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt"


def _smoke_train_detector(coco_json: Path, images_dir: Path, output_dir: Path) -> Path:
    """Treina um detector de objetos por 1 época sobre poucas imagens reais.

    Suficiente para produzir um peso carregável com as classes corretas —
    não é uma validação de metodologia de treino (isso é papel do notebook em
    `training/`), só uma forma rápida e real (não mockada) de exercitar o
    código de inferência do backend contra um modelo de verdade.
    """
    import json
    import urllib.request

    from ultralytics import YOLO
    from ultralytics.data.converter import convert_coco

    data = json.loads(coco_json.read_text(encoding="utf-8"))
    category_names = {cat["id"] - 1: cat["name"] for cat in data["categories"]}

    coco_src = output_dir / "coco_src"
    coco_src.mkdir(parents=True, exist_ok=True)
    shutil.copy(coco_json, coco_src / coco_json.name)

    yolo_dir = output_dir / "yolo"
    convert_coco(
        labels_dir=str(coco_src),
        save_dir=str(yolo_dir),
        use_segments=False,
        use_keypoints=False,
        cls91to80=False,
    )
    (yolo_dir / "labels" / coco_json.stem).rename(yolo_dir / "labels" / "train")

    images_train = yolo_dir / "images" / "train"
    images_train.mkdir(parents=True, exist_ok=True)
    for image in data["images"]:
        src = images_dir / image["file_name"]
        dst = images_train / image["file_name"]
        if not dst.exists():
            dst.symlink_to(src)

    names_yaml = "".join(f"  {idx}: {name}\n" for idx, name in sorted(category_names.items()))
    dataset_yaml = yolo_dir / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {yolo_dir}\ntrain: images/train\nval: images/train\nnames:\n{names_yaml}",
        encoding="utf-8",
    )

    base_weights_dir = output_dir / "base_weights"
    base_weights_dir.mkdir(parents=True, exist_ok=True)
    base_weights = base_weights_dir / "yolov8n.pt"
    if not base_weights.is_file():
        urllib.request.urlretrieve(_YOLO_BASE_WEIGHTS_URL, base_weights)

    model = YOLO(str(base_weights))
    results = model.train(
        data=str(dataset_yaml),
        epochs=1,
        imgsz=320,
        project=str(output_dir / "runs"),
        name="smoke",
        exist_ok=True,
        verbose=False,
        plots=False,
        workers=1,
    )
    return Path(results.save_dir) / "weights" / "best.pt"


@pytest.fixture(scope="session")
def finetuned_weights(tmp_path_factory):
    """Treina uma vez (escopo `session`) e reaproveita entre os testes de detecção."""
    import json

    data = json.loads(_ENDOSCAPES_COCO_JSON.read_text(encoding="utf-8"))
    annotated_ids = {a["image_id"] for a in data["annotations"]}
    chosen = [im for im in data["images"] if im["id"] in annotated_ids][:20]
    chosen_ids = {im["id"] for im in chosen}
    chosen_anns = [a for a in data["annotations"] if a["image_id"] in chosen_ids]
    reduced = {"images": chosen, "annotations": chosen_anns, "categories": data["categories"]}

    work = tmp_path_factory.mktemp("smoke_train_session")
    coco_path = work / "annotation_coco_reduzido.json"
    coco_path.write_text(json.dumps(reduced), encoding="utf-8")

    return _smoke_train_detector(coco_path, _ENDOSCAPES_TRAIN, work / "out")
