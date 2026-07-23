"""Testes de require_tools e das variáveis do topo."""


def test_todas_as_ferramentas_presentes_passa(run, stubbin):
    path = stubbin(["curl", "wget", "unzip"])

    r = run("require_tools", path=path)

    assert r.returncode == 0


def test_curl_ausente_falha_nomeando_a_ferramenta(run, stubbin):
    path = stubbin(["wget", "unzip"])  # sem curl

    r = run("require_tools", path=path)

    assert r.returncode != 0
    assert "curl" in r.stderr


def test_wget_ausente_falha_nomeando_a_ferramenta(run, stubbin):
    path = stubbin(["curl", "unzip"])  # sem wget

    r = run("require_tools", path=path)

    assert r.returncode != 0
    assert "wget" in r.stderr


def test_unzip_ausente_falha_nomeando_a_ferramenta(run, stubbin):
    path = stubbin(["curl", "wget"])  # sem unzip

    r = run("require_tools", path=path)

    assert r.returncode != 0
    assert "unzip" in r.stderr


def test_python_do_venv_ausente_falha(run, stubbin):
    path = stubbin(["curl", "wget", "unzip"])

    r = run("require_tools", path=path, env={"PY": "/nao/existe/python"})

    assert r.returncode != 0
    assert "python" in r.stderr.lower()


def test_variaveis_do_topo_tem_defaults(run, stubbin):
    path = stubbin(["curl", "wget", "unzip"])

    r = run('echo "$ICBHI_DATAVERSE_URL|$ENDOSCAPES_URL|$CTU_DB|$DATA_DIR"', path=path)

    assert r.returncode == 0
    assert "dataverse.harvard.edu" in r.stdout
    assert "endoscapes.zip" in r.stdout
    assert "ctu-uhb-ctgdb" in r.stdout


def test_source_nao_dispara_main(run, stubbin):
    """Sourcing só define funções — não deve tentar baixar nada."""
    path = stubbin(["curl", "wget", "unzip"])

    r = run('echo "sourced-ok"', path=path)

    assert r.returncode == 0
    assert "sourced-ok" in r.stdout


def test_make_data_invoca_o_script():
    from pathlib import Path

    mk = Path(__file__).resolve().parents[3] / "Makefile"
    texto = mk.read_text(encoding="utf-8")
    assert "backend/scripts/download_datasets.sh" in texto
