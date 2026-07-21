"""Testes de `object_loader.load_annotated_frames` -- derivados de VIDEO-06."""

import json
from pathlib import Path

from pipelines.video.object_loader import load_annotated_frames

_ENDOSCAPES_TRAIN = (
    Path(__file__).resolve().parents[3] / "data" / "endoscapes" / "endoscapes" / "train"
)
_COCO_JSON = _ENDOSCAPES_TRAIN / "annotation_coco.json"


def test_carrega_todos_os_frames_reais_do_endoscapes():
    frames = load_annotated_frames(_COCO_JSON, _ENDOSCAPES_TRAIN)

    assert len(frames) == 1212
    assert all(f.image_path.is_file() for f in frames)


def test_frame_real_com_anotacao_conhecida_tem_a_caixa_correta():
    frames = load_annotated_frames(_COCO_JSON, _ENDOSCAPES_TRAIN)

    alvo = next(f for f in frames if f.image_path.name == "8_14775.jpg")

    nomes = {b.class_name for b in alvo.boxes}
    assert "calot_triangle" in nomes
    assert "cystic_artery" in nomes

    calot = next(b for b in alvo.boxes if b.class_name == "calot_triangle")
    assert (calot.x, calot.y, calot.width, calot.height) == (453.0, 208.0, 124.0, 55.0)


def test_frame_real_sem_anotacao_gera_boxes_vazio_sem_ser_descartado():
    frames = load_annotated_frames(_COCO_JSON, _ENDOSCAPES_TRAIN)

    sem_estrutura = next(f for f in frames if f.image_path.name == "10_20350.jpg")

    assert sem_estrutura.boxes == []


def test_mapeamento_de_categoria_usa_secao_categories_nao_indice(tmp_path):
    # Categorias fora de ordem sequencial de índice/id -- um mapeamento por
    # posição na lista (índice) em vez de por `id` real produziria o nome
    # errado aqui.
    coco = {
        "images": [{"id": 1, "file_name": "frame1.jpg"}],
        "annotations": [{"image_id": 1, "category_id": 9, "bbox": [1.0, 2.0, 3.0, 4.0]}],
        "categories": [
            {"id": 9, "name": "tool"},
            {"id": 2, "name": "gallbladder"},
        ],
    }
    coco_path = tmp_path / "annotation_coco.json"
    coco_path.write_text(json.dumps(coco), encoding="utf-8")
    (tmp_path / "frame1.jpg").write_bytes(b"")

    frames = load_annotated_frames(coco_path, tmp_path)

    assert len(frames) == 1
    assert frames[0].boxes[0].class_name == "tool"
