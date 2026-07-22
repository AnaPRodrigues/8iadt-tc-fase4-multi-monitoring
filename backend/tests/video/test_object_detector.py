"""Testes de `object_detector` -- detecção real via YOLOv8 fine-tuned (T8)."""

import json
from pathlib import Path

from pipelines.video.models import Detection
from pipelines.video.object_detector import (
    CRITICAL_STRUCTURES,
    YoloDetector,
    save_critical_structure_evidence,
)

_ENDOSCAPES_TRAIN = (
    Path(__file__).resolve().parents[3] / "data" / "endoscapes" / "endoscapes" / "train"
)
_FRAME = _ENDOSCAPES_TRAIN / "8_14775.jpg"


def test_detect_com_pesos_reais_devolve_deteccoes_com_tipos_validos(finetuned_weights):
    detector = YoloDetector(finetuned_weights)

    detections = detector.detect(_FRAME)

    assert isinstance(detections, list)
    for det in detections:
        assert isinstance(det, Detection)
        assert det.class_name in {
            "cystic_plate",
            "calot_triangle",
            "cystic_artery",
            "cystic_duct",
            "gallbladder",
            "tool",
        }
        assert 0.0 <= det.confidence <= 1.0
        assert len(det.bbox) == 4


def test_detect_sem_nenhuma_deteccao_devolve_lista_vazia_nao_erro(finetuned_weights):
    detector = YoloDetector(finetuned_weights, confidence_threshold=0.999)

    detections = detector.detect(_FRAME)

    assert detections == []


def test_estrutura_critica_detectada_gera_evidencia_com_metadados(tmp_path):
    detections = [
        Detection(class_name="cystic_artery", confidence=0.91, bbox=(453.0, 208.0, 124.0, 55.0)),
        Detection(class_name="tool", confidence=0.5, bbox=(10.0, 10.0, 20.0, 20.0)),
    ]

    evidence = save_critical_structure_evidence(
        image_path=_FRAME, detections=detections, run_id="run1", root=tmp_path
    )

    assert evidence is not None
    assert evidence.artifact_path.is_file()
    assert evidence.sidecar_path.is_file()
    sidecar = json.loads(evidence.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["metadata"]["detections"] == [
        {"class_name": "cystic_artery", "confidence": 0.91, "bbox": [453.0, 208.0, 124.0, 55.0]}
    ]


def test_sem_estrutura_critica_nao_gera_evidencia(tmp_path):
    detections = [Detection(class_name="tool", confidence=0.5, bbox=(10.0, 10.0, 20.0, 20.0))]
    assert "tool" not in CRITICAL_STRUCTURES

    evidence = save_critical_structure_evidence(
        image_path=_FRAME, detections=detections, run_id="run1", root=tmp_path
    )

    assert evidence is None
    assert not (tmp_path / "video_object").exists()
