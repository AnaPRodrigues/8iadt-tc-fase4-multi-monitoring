"""Testes de `pose_evaluate.evaluate` -- derivados de VIDEO-04."""

from pipelines.video.models import SequenceVerdict
from pipelines.video.pose_evaluate import evaluate


def _verdict(seq_id: str, predicted: str, label: str) -> SequenceVerdict:
    return SequenceVerdict(seq_id=seq_id, predicted=predicted, label=label)


def test_conjunto_misto_bate_com_o_rotulo_real():
    verdicts = [
        _verdict("fall-01", "queda", "fall"),  # TP
        _verdict("fall-02", "adl", "fall"),  # FN
        _verdict("adl-01", "adl", "adl"),  # TN
        _verdict("adl-02", "queda", "adl"),  # FP
    ]

    report = evaluate(verdicts)

    assert report.precision == 0.5  # TP=1, FP=1
    assert report.recall == 0.5  # TP=1, FN=1
    assert report.support == 2  # 2 sequências realmente "fall"


def test_dados_insuficientes_excluido_do_calculo():
    # Sem exclusão, o veredito "dados_insuficientes" de uma sequência com
    # label "fall" contaria como falso negativo (support=2, recall=0.5).
    # Excluído corretamente, vira support=1, recall=1.0 -- os dois resultados
    # são diferentes o bastante para o teste discriminar uma implementação
    # que esqueceu o filtro.
    verdicts = [
        _verdict("fall-01", "queda", "fall"),
        _verdict("fall-02", "dados_insuficientes", "fall"),
    ]

    report = evaluate(verdicts)

    assert report.support == 1
    assert report.recall == 1.0
    assert report.precision == 1.0


def test_nenhuma_queda_real_no_conjunto_recall_indefinido():
    verdicts = [
        _verdict("adl-01", "adl", "adl"),
        _verdict("adl-02", "queda", "adl"),  # falso positivo, mas nenhum "fall" real
    ]

    report = evaluate(verdicts)

    assert report.support == 0
    assert report.recall is None  # indefinido, nunca 0.0 (nenhum positivo real)


def test_todos_dados_insuficientes_produz_conjunto_vazio():
    verdicts = [
        _verdict("fall-01", "dados_insuficientes", "fall"),
        _verdict("adl-01", "dados_insuficientes", "adl"),
    ]

    report = evaluate(verdicts)

    assert report.support == 0
    assert report.precision is None
    assert report.recall is None
