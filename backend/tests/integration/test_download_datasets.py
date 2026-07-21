"""Integração das aquisições da F0 com downloaders dublados (sem download real)."""

import stat

import pytest

pytestmark = pytest.mark.integration


def _stub(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return p


def _call(run, func, env):
    """Roda a função, captura o rc real (não o do echo) e o FETCH_STATUS."""
    r = run(f'{func}; rc=$?; echo "RC=$rc STATUS=$FETCH_STATUS"', env=env)
    rc = None
    status = None
    for tok in r.stdout.split():
        if tok.startswith("RC="):
            rc = int(tok[3:])
        elif tok.startswith("STATUS="):
            status = tok[7:]
    return rc, status, r


# ---------- CTU-UHB (T4) ----------

_PY_OK = 'test -n "$CTU_DEST"\n: > "$CTU_DEST/1001.hea"\n: > "$CTU_DEST/1001.dat"\n'
_PY_VAZIO = "exit 0\n"  # roda mas não cria nada
_PY_FALHA = "exit 1\n"


def test_ctu_sucesso_marca_completo(run, tmp_path):
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_ok", _PY_OK)

    rc, status, _ = _call(run, "fetch_ctu_uhb", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc == 0
    assert status == "baixado"
    assert (data / "ctu-uhb" / ".complete").is_file()
    assert (data / "ctu-uhb" / "1001.hea").is_file()


def test_ctu_download_vazio_nao_marca_completo(run, tmp_path):
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_vazio", _PY_VAZIO)

    rc, status, _ = _call(run, "fetch_ctu_uhb", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc != 0
    assert status == "falhou"
    assert not (data / "ctu-uhb" / ".complete").exists()


def test_ctu_python_falha_nao_marca_completo(run, tmp_path):
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_falha", _PY_FALHA)

    rc, status, _ = _call(run, "fetch_ctu_uhb", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc != 0
    assert not (data / "ctu-uhb" / ".complete").exists()


def test_ctu_ja_completo_pula_sem_rodar_python(run, tmp_path):
    data = tmp_path / "data"
    dest = data / "ctu-uhb"
    dest.mkdir(parents=True)
    (dest / ".complete").touch()
    # stub que deixa marca se for executado
    py = _stub(tmp_path, "py_marca", ': > "$CTU_DEST/STUB_RAN"\n')

    rc, status, _ = _call(run, "fetch_ctu_uhb", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc == 0
    assert status == "pulado"
    assert not (dest / "STUB_RAN").exists()  # não rebaixou
