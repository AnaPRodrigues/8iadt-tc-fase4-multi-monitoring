"""Prepara, localmente, o subconjunto de imagens do Endoscapes a subir para o Drive.

Roda FORA do Colab, na máquina que já tem `data/endoscapes/` baixado (`make data`).
O diretório `train/` do Endoscapes tem 36694 `.jpg`, mas cada `annotation_coco.json`
referencia só o subconjunto anotado (1212 em train, 409 em val, 312 em test) -- subir
o diretório inteiro violaria o requisito de treino (AD-042) de não subir o dataset
bruto de ~6 GB ao Drive.

Reusa `pipelines.video.object_loader.load_annotated_frames` (mesmo parser de F1) para
descobrir exatamente quais arquivos estão referenciados -- não reimplementa o parsing
do COCO.

Uso:
    PYTHONPATH=backend .venv/bin/python training/prepare_dataset_subset.py

Saída: `training/staging/<split>/` com os JPEGs referenciados + o `annotation_coco.json`
do split, prontos para zipar e subir ao Drive.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from pipelines.video.object_loader import load_annotated_frames  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATASET_ROOT = _REPO_ROOT / "data" / "endoscapes" / "endoscapes"
_STAGING_ROOT = Path(__file__).resolve().parent / "staging"

_SPLITS = ("train", "val", "test")


def stage_split(split: str) -> int:
    coco_json = _DATASET_ROOT / split / "annotation_coco.json"
    images_dir = _DATASET_ROOT / split
    if not coco_json.is_file():
        raise FileNotFoundError(
            f"{coco_json} ausente -- rode `make data` antes de preparar o subconjunto"
        )

    frames = load_annotated_frames(coco_json, images_dir)

    dest_dir = _STAGING_ROOT / split
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(coco_json, dest_dir / "annotation_coco.json")

    copiadas = 0
    for frame in frames:
        dest = dest_dir / frame.image_path.name
        if not dest.exists():
            shutil.copy2(frame.image_path, dest)
        copiadas += 1

    return copiadas


def main() -> int:
    total = 0
    for split in _SPLITS:
        n = stage_split(split)
        print(f"{split}: {n} imagem(ns) + annotation_coco.json em {_STAGING_ROOT / split}")
        total += n

    print(f"\nTotal: {total} imagens em {_STAGING_ROOT}")
    print("Próximo passo: zipar training/staging/ e subir ao Google Drive (ver training/README.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
