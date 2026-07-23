"""Testes de `adapters.YoloImageAnalyzer`/`register_local_adapters`."""

from pathlib import Path

from aws.adapters import ImageAnalysis, ImageLabel, get_image_analyzer
from pipelines.video.adapters import YoloImageAnalyzer, register_local_adapters
from pipelines.video.object_detector import YoloDetector

_ENDOSCAPES_TRAIN = (
    Path(__file__).resolve().parents[3] / "data" / "endoscapes" / "endoscapes" / "train"
)
_FRAME = _ENDOSCAPES_TRAIN / "8_14775.jpg"


def test_analyze_usa_yolodetector_e_devolve_imagelabels_por_deteccao(finetuned_weights):
    analyzer = YoloImageAnalyzer(finetuned_weights)

    result = analyzer.analyze(_FRAME.read_bytes())

    assert isinstance(result, ImageAnalysis)
    for label in result.labels:
        assert isinstance(label, ImageLabel)
        assert isinstance(label.name, str)
        assert 0.0 <= label.confidence <= 1.0


def test_labels_do_analyze_batem_com_o_que_yolodetector_devolveria(finetuned_weights):
    analyzer = YoloImageAnalyzer(finetuned_weights)
    detector = YoloDetector(finetuned_weights)

    result = analyzer.analyze(_FRAME.read_bytes())
    detections = detector.detect(_FRAME)

    assert [(lbl.name, lbl.confidence) for lbl in result.labels] == [
        (d.class_name, d.confidence) for d in detections
    ]


def test_register_local_adapters_registra_yoloimageanalyzer_para_env_local(finetuned_weights):
    register_local_adapters(finetuned_weights)

    analyzer = get_image_analyzer("local")

    assert isinstance(analyzer, YoloImageAnalyzer)
