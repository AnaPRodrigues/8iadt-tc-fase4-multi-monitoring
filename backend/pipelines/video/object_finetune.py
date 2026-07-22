"""Fine-tuning leve do YOLOv8n sobre as classes reais do Endoscapes (VIDEO-07/08).

Dois cuidados confirmados no Design, não presumir de novo:
- `ultralytics.data.converter.convert_coco` faz glob de todo `*.json` no
  diretório informado -- o diretório real do Endoscapes tem mais de um JSON
  de anotação (`annotation_coco.json`, `annotation_ds_coco.json`,
  `annotation_coco_vid.json`), então o COCO de entrada é sempre isolado num
  diretório próprio antes da conversão.
- `ultralytics.YOLO("yolov8n.pt")` e `model.train(...)` por padrão escrevem
  relativo ao cwd do processo (peso solto, `runs/`) -- os pesos base vão para
  um cache absoluto dentro de `output_dir` e o treino recebe `project=`/
  `name=` explícitos, nunca o padrão do ultralytics.
"""

import json
import shutil
import urllib.request
from pathlib import Path

from ultralytics import YOLO
from ultralytics.data.converter import convert_coco

from common.logging import get_logger

log = get_logger("video.object_finetune")

_WEIGHTS_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt"
_WEIGHTS_FILENAME = "yolov8n.pt"


def ensure_base_weights(cache_dir: Path) -> Path:
    """Baixa o peso base do YOLOv8n sob demanda; idempotente.

    Mesmo princípio de `pose.ensure_pose_model`: o caminho de destino é
    sempre absoluto e explícito, nunca o nome relativo que o ultralytics
    resolveria contra o cwd do processo.
    """
    cache_dir = Path(cache_dir)
    weights_path = cache_dir / _WEIGHTS_FILENAME
    if weights_path.is_file():
        log.info("pesos base já em cache: %s", weights_path)
        return weights_path

    cache_dir.mkdir(parents=True, exist_ok=True)
    log.info("baixando pesos base de %s", _WEIGHTS_URL)
    try:
        urllib.request.urlretrieve(_WEIGHTS_URL, weights_path)
    except Exception as exc:
        raise RuntimeError(f"falha ao baixar os pesos base de {_WEIGHTS_URL}: {exc}") from exc

    return weights_path


def finetune(
    coco_json: Path,
    images_dir: Path,
    output_dir: Path,
    epochs: int = 1,
    imgsz: int = 320,
) -> Path:
    """Converte a anotação COCO real para YOLO e treina, devolvendo `best.pt`.

    `output_dir` concentra todo o resultado (dataset convertido, cache de
    pesos base, `runs/` de treino) -- nunca escreve no cwd do processo.
    """
    coco_json = Path(coco_json)
    images_dir = Path(images_dir)
    output_dir = Path(output_dir)

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

    labels_src = yolo_dir / "labels" / coco_json.stem
    labels_train = yolo_dir / "labels" / "train"
    labels_src.rename(labels_train)

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

    base_weights = ensure_base_weights(output_dir / "models")
    model = YOLO(str(base_weights))
    results = model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        imgsz=imgsz,
        project=str(output_dir / "runs"),
        name="finetune",
        exist_ok=True,
        verbose=False,
        plots=False,
        workers=1,
    )

    best_path = Path(results.save_dir) / "weights" / "best.pt"
    log.info("fine-tuning concluído: %s", best_path)
    return best_path
