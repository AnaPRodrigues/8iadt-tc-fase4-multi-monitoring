"""Precision/recall/F1 por classe da raia objeto, via casamento IoU.

Limiar de IoU escolhido como 0.5 -- convenção comum de detecção de objetos
(ex.: COCO/Pascal VOC); aceitável também para as estruturas do Endoscapes,
cujas caixas (estruturas anatômicas) tendem a ser maiores/mais difusas que
objetos COCO típicos, o que torna 0.5 uma exigência já razoavelmente
tolerante, não mais rígida que o caso típico.

Persistência do relatório reaproveita `common.metrics.save_report`
diretamente -- mesmo princípio de `pose_evaluate.py`.
"""

from collections import defaultdict
from pathlib import Path

from common.logging import get_logger
from common.metrics import MetricsReport, binary_metrics
from pipelines.video.models import AnnotatedFrame, BoundingBox, Detection

log = get_logger("video.object_evaluate")

IOU_THRESHOLD = 0.5


def iou(
    box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]
) -> float:
    """IoU de duas caixas no formato COCO (x, y, width, height)."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax + aw, bx + bw)
    inter_y2 = min(ay + ah, by + bh)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    union_area = aw * ah + bw * bh - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def _box_tuple(box: BoundingBox) -> tuple[float, float, float, float]:
    return (box.x, box.y, box.width, box.height)


def evaluate(
    annotated_frames: list[AnnotatedFrame],
    detections_by_frame: dict[Path, list[Detection]],
    classes: set[str] | None = None,
    iou_threshold: float = IOU_THRESHOLD,
) -> dict[str, MetricsReport]:
    """Casa detecção<->caixa real por IoU >= `iou_threshold`, um relatório por classe.

    `classes` é o universo avaliado; por padrão é derivado dos dados (união das
    classes anotadas + detectadas). Uma classe sem nenhuma instância real nem
    detecção no subconjunto avaliado (ex.: passada explicitamente em `classes`)
    tem `support=0` e métricas `None` -- indefinido, não zero.
    """
    if classes is None:
        classes = {box.class_name for frame in annotated_frames for box in frame.boxes}
        classes |= {d.class_name for dets in detections_by_frame.values() for d in dets}

    y_true_by_class: dict[str, list[bool]] = defaultdict(list)
    y_pred_by_class: dict[str, list[bool]] = defaultdict(list)

    for frame in annotated_frames:
        detections = detections_by_frame.get(frame.image_path, [])
        for class_name in classes:
            gt_boxes = [box for box in frame.boxes if box.class_name == class_name]
            dets = sorted(
                (d for d in detections if d.class_name == class_name),
                key=lambda d: d.confidence,
                reverse=True,
            )

            matched = [False] * len(gt_boxes)
            for det in dets:
                best_idx, best_iou = -1, 0.0
                for idx, gt in enumerate(gt_boxes):
                    if matched[idx]:
                        continue
                    score = iou(det.bbox, _box_tuple(gt))
                    if score > best_iou:
                        best_idx, best_iou = idx, score

                if best_idx >= 0 and best_iou >= iou_threshold:
                    matched[best_idx] = True
                    y_true_by_class[class_name].append(True)
                    y_pred_by_class[class_name].append(True)
                else:
                    y_true_by_class[class_name].append(False)
                    y_pred_by_class[class_name].append(True)

            for was_matched in matched:
                if not was_matched:
                    y_true_by_class[class_name].append(True)
                    y_pred_by_class[class_name].append(False)

    return {
        class_name: binary_metrics(
            y_true_by_class[class_name], y_pred_by_class[class_name], detector=class_name
        )
        for class_name in sorted(classes)
    }
