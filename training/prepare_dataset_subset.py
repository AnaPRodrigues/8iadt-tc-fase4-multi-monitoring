"""Prepara, localmente, o subconjunto de imagens do dataset cirúrgico a subir ao Drive.

Roda FORA do Colab, na máquina que já tem o dataset de imagens cirúrgicas anotadas
baixado. Autocontido: não importa nada do resto do repositório, só a biblioteca
padrão do Python — lê o arquivo de anotação (formato COCO) e copia apenas as
imagens nele referenciadas, sem depender de nenhum código do sistema em produção.

O diretório de imagens de treino do dataset original tem dezenas de milhares de
arquivos, mas o arquivo de anotação só referencia um subconjunto (as imagens de
fato rotuladas com as estruturas anatômicas de interesse) — subir o diretório
inteiro ao Drive seria um upload de vários gigabytes desnecessário; subir só o
subconjunto anotado reduz isso para algumas centenas de megabytes.

Uso:
    python3 training/prepare_dataset_subset.py

Saída: `training/staging/<split>/` com as imagens referenciadas + o arquivo de
anotação de cada split, prontos para zipar e subir ao Google Drive.
"""

import json
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATASET_ROOT = _REPO_ROOT / "data" / "endoscapes" / "endoscapes"
_STAGING_ROOT = Path(__file__).resolve().parent / "staging"

_SPLITS = ("train", "val", "test")


def _referenced_filenames(coco_json: Path) -> list[str]:
    data = json.loads(coco_json.read_text(encoding="utf-8"))
    return [image["file_name"] for image in data["images"]]


def stage_split(split: str) -> int:
    coco_json = _DATASET_ROOT / split / "annotation_coco.json"
    images_dir = _DATASET_ROOT / split
    if not coco_json.is_file():
        raise FileNotFoundError(
            f"{coco_json} ausente -- baixe o dataset de imagens cirúrgicas antes de preparar "
            f"o subconjunto (ver o README principal do repositório)"
        )

    filenames = _referenced_filenames(coco_json)

    dest_dir = _STAGING_ROOT / split
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(coco_json, dest_dir / "annotation_coco.json")

    copiadas = 0
    for filename in filenames:
        src = images_dir / filename
        dst = dest_dir / filename
        if not dst.exists():
            shutil.copy2(src, dst)
        copiadas += 1

    return copiadas


def main() -> int:
    total = 0
    for split in _SPLITS:
        n = stage_split(split)
        print(f"{split}: {n} imagem(ns) + arquivo de anotação em {_STAGING_ROOT / split}")
        total += n

    print(f"\nTotal: {total} imagens em {_STAGING_ROOT}")
    print("Próximo passo: zipar training/staging/ e subir ao Google Drive (ver training/README.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
