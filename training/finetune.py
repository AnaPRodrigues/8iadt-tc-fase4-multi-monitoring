"""Treino do detector de objetos (YOLOv8) sobre frames cirúrgicos anotados.

Módulo autocontido: só depende do `ultralytics` (biblioteca de treino) e da
biblioteca padrão do Python. Não importa nada do resto do repositório — é o
único lugar do projeto que treina um modelo; o sistema em produção só carrega
o peso pronto e faz inferência.

Espera um dataset no formato COCO (uma pasta com `annotation_coco.json` +
as imagens referenciadas) para cada split — treino, validação e teste.
"""

import json
import logging
import shutil
import urllib.request
from pathlib import Path

from ultralytics import YOLO
from ultralytics.data.converter import convert_coco

log = logging.getLogger("training.finetune")

_WEIGHTS_BASE_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0"


def ensure_base_weights(cache_dir: Path, model_variant: str = "yolov8n") -> Path:
    """Baixa o peso pré-treinado do `model_variant` sob demanda; não baixa de novo se já existir."""
    cache_dir = Path(cache_dir)
    weights_filename = f"{model_variant}.pt"
    weights_path = cache_dir / weights_filename
    if weights_path.is_file():
        log.info("pesos base já em cache: %s", weights_path)
        return weights_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    weights_url = f"{_WEIGHTS_BASE_URL}/{weights_filename}"
    log.info("baixando pesos base de %s", weights_url)
    try:
        urllib.request.urlretrieve(weights_url, weights_path)
    except Exception as exc:
        raise RuntimeError(f"falha ao baixar os pesos base de {weights_url}: {exc}") from exc

    return weights_path


def coco_categories(coco_json: Path) -> dict[int, str]:
    data = json.loads(coco_json.read_text(encoding="utf-8"))
    return {cat["id"] - 1: cat["name"] for cat in data["categories"]}


def convert_split(coco_json: Path, images_dir: Path, yolo_dir: Path, split: str) -> None:
    """Converte um split COCO (train/val/test) para o formato de rótulo do YOLO.

    Função pública porque quem for avaliar contra um terceiro split (teste,
    nunca usado no treino) precisa dela também -- ver o notebook, que a chama
    depois de `finetune()` para preparar a avaliação final.

    `convert_coco` faz glob de todo `*.json` no diretório informado -- por
    isso o COCO de entrada é sempre isolado num diretório próprio antes da
    conversão, mesmo quando o dataset original tem mais de um arquivo de
    anotação na mesma pasta (é o caso do dataset cirúrgico usado aqui).
    """
    data = json.loads(coco_json.read_text(encoding="utf-8"))

    coco_src = yolo_dir / f"_coco_src_{split}"
    coco_src.mkdir(parents=True, exist_ok=True)
    shutil.copy(coco_json, coco_src / coco_json.name)

    convert_coco(
        labels_dir=str(coco_src),
        save_dir=str(yolo_dir / f"_tmp_{split}"),
        use_segments=False,
        use_keypoints=False,
        cls91to80=False,
    )

    labels_dst = yolo_dir / "labels" / split
    labels_dst.parent.mkdir(parents=True, exist_ok=True)
    (yolo_dir / f"_tmp_{split}" / "labels" / coco_json.stem).rename(labels_dst)
    shutil.rmtree(yolo_dir / f"_tmp_{split}")
    shutil.rmtree(coco_src)

    images_dst = yolo_dir / "images" / split
    images_dst.mkdir(parents=True, exist_ok=True)
    for image in data["images"]:
        src = images_dir / image["file_name"]
        dst = images_dst / image["file_name"]
        if not dst.exists():
            dst.symlink_to(src)


def finetune(
    train_coco: Path,
    train_images: Path,
    val_coco: Path,
    val_images: Path,
    output_dir: Path,
    model_variant: str = "yolov8n",
    epochs: int = 50,
    imgsz: int = 640,
    seed: int = 42,
) -> Path:
    """Converte treino+validação para YOLO e treina, devolvendo o caminho de `best.pt`.

    Usa um split de validação de verdade (nunca o próprio treino) para o
    early-stopping interno do treino -- a avaliação final e honesta contra um
    terceiro split (teste), nunca visto aqui, fica por conta de quem chama
    este módulo (ver `train_yolo_endoscapes.ipynb`, que usa `model.val(...,
    split="test")` depois de treinar).

    `model_variant` seleciona o tamanho do modelo base pré-treinado (ex.:
    `"yolov8n"`, `"yolov8s"`) -- quem chama pode treinar mais de um variante
    sobre o mesmo `output_dir` e comparar depois; cada treino grava em
    `runs/finetune_<model_variant>/`, então variantes diferentes não se
    sobrescrevem.

    `output_dir` concentra todo o resultado (dataset convertido, cache de
    pesos base, saída do treino) -- nunca escreve no diretório de trabalho
    corrente do processo.
    """
    train_coco, train_images = Path(train_coco), Path(train_images)
    val_coco, val_images = Path(val_coco), Path(val_images)
    output_dir = Path(output_dir)

    category_names = coco_categories(train_coco)

    yolo_dir = output_dir / "yolo"
    convert_split(train_coco, train_images, yolo_dir, "train")
    convert_split(val_coco, val_images, yolo_dir, "val")

    names_yaml = "".join(f"  {idx}: {name}\n" for idx, name in sorted(category_names.items()))
    dataset_yaml = yolo_dir / "dataset.yaml"
    dataset_yaml.write_text(
        f"path: {yolo_dir}\ntrain: images/train\nval: images/val\nnames:\n{names_yaml}",
        encoding="utf-8",
    )

    base_weights = ensure_base_weights(output_dir / "base_weights", model_variant)
    model = YOLO(str(base_weights))
    results = model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        seed=seed,
        project=str(output_dir / "runs"),
        name=f"finetune_{model_variant}",
        exist_ok=True,
        verbose=False,
        plots=False,
        workers=1,
    )

    best_path = Path(results.save_dir) / "weights" / "best.pt"
    log.info("treino concluído: %s", best_path)
    return best_path
