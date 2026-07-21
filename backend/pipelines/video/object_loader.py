"""Carga de frames + anotação COCO real do Endoscapes-BBox201 (VIDEO-06)."""

import json
from pathlib import Path

from common.logging import get_logger
from pipelines.video.models import AnnotatedFrame, BoundingBox

log = get_logger("video.object_loader")


def load_annotated_frames(coco_json: Path, images_dir: Path) -> list[AnnotatedFrame]:
    """Parseia o COCO real, mapeando `category_id` -> nome via `categories`.

    Nunca deriva o nome a partir do índice na lista -- só da seção
    `categories` do próprio JSON. Um frame listado em `images` sem nenhuma
    anotação em `annotations` vira `AnnotatedFrame(boxes=[])`, legitimamente
    sem estrutura anotada, nunca descartado do lote.
    """
    coco_json = Path(coco_json)
    images_dir = Path(images_dir)

    data = json.loads(coco_json.read_text(encoding="utf-8"))

    category_names = {cat["id"]: cat["name"] for cat in data["categories"]}

    boxes_by_image: dict[int, list[BoundingBox]] = {}
    for ann in data["annotations"]:
        x, y, width, height = ann["bbox"]
        box = BoundingBox(
            class_name=category_names[ann["category_id"]],
            x=float(x),
            y=float(y),
            width=float(width),
            height=float(height),
        )
        boxes_by_image.setdefault(ann["image_id"], []).append(box)

    frames = [
        AnnotatedFrame(
            image_path=images_dir / image["file_name"],
            boxes=boxes_by_image.get(image["id"], []),
        )
        for image in data["images"]
    ]

    log.info("%d frame(s) carregado(s) de %s", len(frames), coco_json)
    return frames
