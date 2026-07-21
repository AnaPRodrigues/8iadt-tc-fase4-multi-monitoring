"""Integração das aquisições da F0 com downloaders dublados (sem download real)."""

import os
import stat
import zipfile

import pytest

pytestmark = pytest.mark.integration


def _stub(tmp_path, name, body):
    p = tmp_path / name
    p.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return p


def _zip_fixture(path):
    """Zip real (entrada incompressível) que passa no verify_zip."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("registro.wav", os.urandom(5000))
    return path


# curl dublado: escolhe o comportamento por trecho da URL, via env
# DATAVERSE_MODE / ORIGINAL_MODE ∈ {zip, html, fail}. FIXTURE_ZIP = zip real.
_CURL_STUB = r"""
out=""; prev=""; url=""
for a in "$@"; do
  [ "$prev" = "-o" ] && out="$a"
  case "$a" in http*) url="$a";; esac
  prev="$a"
done
mode=""
case "$url" in
  *dataverse*) mode="$DATAVERSE_MODE";;
  *bhichallenge*) mode="$ORIGINAL_MODE";;
esac
case "$mode" in
  zip)  cp "$FIXTURE_ZIP" "$out";;
  html)
    { printf '<!DOCTYPE html><html>403 '; head -c 2000 /dev/zero | tr '\0' x; } > "$out"
    ;;
  fail) exit 7;;
  *)    exit 8;;
esac
"""


def _path_with(stubdir):
    return f"{stubdir}:{os.environ['PATH']}"


def _call(run, func, env, path=None):
    """Roda a função, captura o rc real (não o do echo) e o FETCH_STATUS."""
    r = run(f'{func}; rc=$?; echo "RC=$rc STATUS=$FETCH_STATUS"', env=env, path=path)
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


# ---------- ICBHI (T5): Dataverse + fallback SSL ----------


def _icbhi_env(tmp_path, dataverse, original):
    data = tmp_path / "data"
    fixture = _zip_fixture(tmp_path / "icbhi_fix.zip")
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    _stub(stubdir, "curl", _CURL_STUB)
    env = {
        "DATA_DIR": str(data),
        "FIXTURE_ZIP": str(fixture),
        "DATAVERSE_MODE": dataverse,
        "ORIGINAL_MODE": original,
    }
    return data, env, _path_with(stubdir)


def test_icbhi_dataverse_entrega_zip(run, tmp_path):
    data, env, path = _icbhi_env(tmp_path, dataverse="zip", original="fail")

    rc, status, _ = _call(run, "fetch_icbhi", env, path)

    assert rc == 0
    assert status == "baixado"
    assert (data / "icbhi" / ".complete").is_file()
    assert (data / "icbhi" / "registro.wav").is_file()  # unzip real ocorreu


def test_icbhi_dataverse_falha_usa_fallback(run, tmp_path):
    data, env, path = _icbhi_env(tmp_path, dataverse="fail", original="zip")

    rc, status, _ = _call(run, "fetch_icbhi", env, path)

    assert rc == 0
    assert status == "baixado"
    assert (data / "icbhi" / ".complete").is_file()


def test_icbhi_dataverse_html_e_rejeitado_e_cai_no_fallback(run, tmp_path):
    # A primária responde HTML (o caso 403); só o fallback entrega zip real.
    data, env, path = _icbhi_env(tmp_path, dataverse="html", original="zip")

    rc, status, _ = _call(run, "fetch_icbhi", env, path)

    assert rc == 0
    assert status == "baixado"
    assert (data / "icbhi" / ".complete").is_file()


def test_icbhi_ambas_falham_nao_marca_completo(run, tmp_path):
    data, env, path = _icbhi_env(tmp_path, dataverse="html", original="fail")

    rc, status, _ = _call(run, "fetch_icbhi", env, path)

    assert rc != 0
    assert status == "falhou"
    assert not (data / "icbhi" / ".complete").exists()
