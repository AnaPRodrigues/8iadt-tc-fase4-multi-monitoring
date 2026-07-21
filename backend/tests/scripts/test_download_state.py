"""Testes da sentinela de idempotência (DATA-07) e da checagem de espaço (DATA-08)."""


def test_is_complete_falso_sem_sentinela(run, tmp_path):
    d = tmp_path / "ds"
    d.mkdir()

    r = run(f"is_complete '{d}'")

    assert r.returncode != 0


def test_mark_complete_cria_sentinela_e_is_complete_passa(run, tmp_path):
    d = tmp_path / "ds"
    d.mkdir()

    r = run(f"mark_complete '{d}' && is_complete '{d}'")

    assert r.returncode == 0
    assert (d / ".complete").is_file()


def test_espaco_suficiente_passa(run, tmp_path):
    # Precisa de 1 byte: sempre há.
    r = run("check_disk_space 1", env={"DATA_DIR": str(tmp_path)})

    assert r.returncode == 0


def test_espaco_insuficiente_falha_com_mensagem(run, tmp_path):
    # 999 TB: força a falha em qualquer disco realista.
    r = run("check_disk_space 999000000000000", env={"DATA_DIR": str(tmp_path)})

    assert r.returncode != 0
    assert "insuficiente" in r.stderr


def test_espaco_em_diretorio_inexistente_falha(run, tmp_path):
    r = run("check_disk_space 1", env={"DATA_DIR": str(tmp_path / "nao-existe")})

    assert r.returncode != 0
