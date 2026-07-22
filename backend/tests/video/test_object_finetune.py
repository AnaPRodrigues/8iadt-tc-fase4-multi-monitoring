"""Testes de `object_finetune.finetune` -- fine-tuning real sobre frames reais (T7).

Execução real intencional (não mockada): a task exige confirmar que o peso
resultante existe e é carregável pelo ultralytics de verdade -- poucas
imagens e poucas épocas para manter o gate rápido (achado do Design: ~10s).
"""

import json
import os
from pathlib import Path

from ultralytics import YOLO

from pipelines.video.object_finetune import finetune

_ENDOSCAPES_TRAIN = (
    Path(__file__).resolve().parents[3] / "data" / "endoscapes" / "endoscapes" / "train"
)
_COCO_JSON = _ENDOSCAPES_TRAIN / "annotation_coco.json"


def _reduced_coco_json(tmp_path: Path, n_images: int) -> Path:
    data = json.loads(_COCO_JSON.read_text(encoding="utf-8"))
    annotated_ids = {a["image_id"] for a in data["annotations"]}
    chosen = [im for im in data["images"] if im["id"] in annotated_ids][:n_images]
    chosen_ids = {im["id"] for im in chosen}
    chosen_anns = [a for a in data["annotations"] if a["image_id"] in chosen_ids]

    reduced = {"images": chosen, "annotations": chosen_anns, "categories": data["categories"]}
    reduced_path = tmp_path / "annotation_coco_reduzido.json"
    reduced_path.write_text(json.dumps(reduced), encoding="utf-8")
    return reduced_path


def test_finetune_real_gera_pesos_carregaveis_com_as_6_classes(tmp_path):
    coco = _reduced_coco_json(tmp_path, n_images=10)

    best_path = finetune(coco, _ENDOSCAPES_TRAIN, tmp_path / "out", epochs=1, imgsz=320)

    assert best_path.is_file()
    model = YOLO(str(best_path))
    assert list(model.names.values()) == [
        "cystic_plate",
        "calot_triangle",
        "cystic_artery",
        "cystic_duct",
        "gallbladder",
        "tool",
    ]


def test_finetune_nao_polui_a_raiz_do_repo(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    antes = set(os.listdir(repo_root))

    coco = _reduced_coco_json(tmp_path, n_images=6)
    finetune(coco, _ENDOSCAPES_TRAIN, tmp_path / "out", epochs=1, imgsz=320)

    depois = set(os.listdir(repo_root))
    assert depois == antes
