"""Testes de require_tools (DATA-11) e das variáveis do topo (DATA-05)."""


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
