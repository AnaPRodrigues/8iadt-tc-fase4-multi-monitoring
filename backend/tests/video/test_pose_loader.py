"""Testes de `pose_loader.load_sequence` -- carga da sequência e do
edge case de ordenação numérica.
"""

from pathlib import Path

import pytest

from pipelines.video.pose_loader import load_sequence

_URFD_ROOT = Path(__file__).resolve().parents[3] / "data" / "urfd"


def test_carrega_sequencia_real_de_queda():
    seq = load_sequence(_URFD_ROOT / "fall-01")

    assert seq.seq_id == "fall-01"
    assert seq.label == "fall"
    assert len(seq.frame_paths) == 160


def test_carrega_sequencia_real_de_adl():
    seq = load_sequence(_URFD_ROOT / "adl-01")

    assert seq.seq_id == "adl-01"
    assert seq.label == "adl"
    assert len(seq.frame_paths) > 0


def test_frames_em_ordem_numerica_estritamente_crescente():
    seq = load_sequence(_URFD_ROOT / "fall-01")

    numeros = [int(p.stem.rsplit("-", 1)[-1]) for p in seq.frame_paths]
    assert numeros == sorted(numeros)
    assert numeros[0] == 1
    assert numeros[-1] == 160


def test_ordenacao_numerica_nao_alfabetica_frame_9_antes_de_10(tmp_path):
    # Nomes sem zero-padding expõem o bug clássico de ordenação alfabética
    # ("...-10.png" viria antes de "...-9.png" em ordem de string).
    seq_dir = tmp_path / "fall-99"
    frames_dir = seq_dir / "fall-99-cam0-rgb"
    frames_dir.mkdir(parents=True)
    for n in [1, 2, 9, 10, 11]:
        (frames_dir / f"fall-99-cam0-rgb-{n}.png").write_bytes(b"")

    seq = load_sequence(seq_dir)

    numeros = [int(p.stem.rsplit("-", 1)[-1]) for p in seq.frame_paths]
    assert numeros == [1, 2, 9, 10, 11]


def test_diretorio_com_nome_desconhecido_levanta_value_error(tmp_path):
    seq_dir = tmp_path / "algo-qualquer-01"
    seq_dir.mkdir()

    with pytest.raises(ValueError):
        load_sequence(seq_dir)


def test_diretorio_de_frames_ausente_levanta_file_not_found_error(tmp_path):
    seq_dir = tmp_path / "fall-77"
    seq_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        load_sequence(seq_dir)
