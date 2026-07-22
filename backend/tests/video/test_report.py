"""Testes de `report.generate_report` (T13)."""

from pathlib import Path

from pipelines.video.report import ReportEvent, generate_report


def test_sequencia_com_eventos_conhecidos_lista_cada_evento():
    eventos_pose = [ReportEvent(frame=42, kind="queda", evidence_path=Path("fall-42.png"))]
    eventos_objeto = [
        ReportEvent(frame=7, kind="estrutura_critica", evidence_path=Path("critical-7.png"))
    ]

    relatorio = generate_report(eventos_pose, eventos_objeto)

    assert "Frame 42" in relatorio
    assert "queda" in relatorio
    assert "fall-42.png" in relatorio
    assert "Frame 7" in relatorio
    assert "estrutura_critica" in relatorio
    assert "critical-7.png" in relatorio


def test_sequencia_sem_eventos_declara_ausencia_explicitamente():
    relatorio = generate_report([], [])

    assert "nenhum evento detectado" in relatorio.lower()


def test_sem_object_result_gera_relatorio_so_com_eventos_de_pose():
    eventos_pose = [ReportEvent(frame=1, kind="queda", evidence_path=Path("fall-1.png"))]

    relatorio = generate_report(eventos_pose)

    assert "Frame 1" in relatorio
    assert "nenhum evento detectado" not in relatorio.lower()


def test_duas_sequencias_processadas_em_sequencia_nao_misturam_dados():
    eventos_a = [ReportEvent(frame=10, kind="queda", evidence_path=Path("a.png"))]
    eventos_b = [
        ReportEvent(frame=99, kind="estrutura_critica", evidence_path=Path("b.png"))
    ]

    relatorio_a1 = generate_report(eventos_a)
    relatorio_b = generate_report(eventos_b)
    relatorio_a2 = generate_report(eventos_a)

    assert relatorio_a1 == relatorio_a2
    assert "10" in relatorio_a1 and "99" not in relatorio_a1
    assert "99" in relatorio_b and "10" not in relatorio_b
