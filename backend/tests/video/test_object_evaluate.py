"""Testes de `object_evaluate.evaluate` -- casamento IoU e métricas por classe."""

from pathlib import Path

from pipelines.video.models import AnnotatedFrame, BoundingBox, Detection
from pipelines.video.object_evaluate import evaluate, iou


def test_deteccao_com_iou_alto_conta_como_acerto():
    frame_path = Path("frame1.jpg")
    frames = [
        AnnotatedFrame(
            image_path=frame_path,
            boxes=[
                BoundingBox(
                    class_name="cystic_artery", x=100.0, y=100.0, width=50.0, height=50.0
                )
            ],
        )
    ]
    detections = {
        frame_path: [
            Detection(class_name="cystic_artery", confidence=0.9, bbox=(102.0, 102.0, 48.0, 48.0))
        ]
    }

    report = evaluate(frames, detections)["cystic_artery"]

    assert report.support == 1
    assert report.precision == 1.0
    assert report.recall == 1.0


def test_deteccao_com_iou_baixo_nao_conta_como_acerto():
    frame_path = Path("frame1.jpg")
    frames = [
        AnnotatedFrame(
            image_path=frame_path,
            boxes=[
                BoundingBox(
                    class_name="cystic_artery", x=100.0, y=100.0, width=50.0, height=50.0
                )
            ],
        )
    ]
    # bbox longe da caixa real -- IoU 0.0, bem abaixo do limiar 0.5
    detections = {
        frame_path: [
            Detection(class_name="cystic_artery", confidence=0.9, bbox=(500.0, 500.0, 20.0, 20.0))
        ]
    }

    report = evaluate(frames, detections)["cystic_artery"]

    assert report.support == 1
    assert report.precision == 0.0
    assert report.recall == 0.0


def test_classe_ausente_do_subconjunto_tem_support_zero_e_metricas_none():
    frame_path = Path("frame1.jpg")
    frames = [
        AnnotatedFrame(
            image_path=frame_path,
            boxes=[
                BoundingBox(
                    class_name="cystic_artery", x=100.0, y=100.0, width=50.0, height=50.0
                )
            ],
        )
    ]
    detections = {
        frame_path: [
            Detection(class_name="cystic_artery", confidence=0.9, bbox=(102.0, 102.0, 48.0, 48.0))
        ]
    }

    report = evaluate(frames, detections, classes={"cystic_artery", "cystic_duct"})["cystic_duct"]

    assert report.support == 0
    assert report.precision is None
    assert report.recall is None
    assert report.f1 is None


def test_iou_de_caixas_identicas_e_1_e_de_caixas_disjuntas_e_0():
    box = (10.0, 10.0, 20.0, 20.0)
    assert iou(box, box) == 1.0
    assert iou(box, (1000.0, 1000.0, 5.0, 5.0)) == 0.0
