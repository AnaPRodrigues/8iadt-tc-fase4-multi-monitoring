"""Integração das aquisições de datasets com downloaders dublados (sem download real)."""

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


# ---------- CTU-UHB ----------

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


# ---------- ICBHI: Dataverse + fallback SSL ----------


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


# ---------- Endoscapes ----------

_WGET_STUB = r"""
out=""; prev=""
for a in "$@"; do
  [ "$prev" = "-O" ] && out="$a"
  prev="$a"
done
case "$ENDO_MODE" in
  zip)     cp "$FIXTURE_ZIP" "$out";;
  invalid) printf 'not a zip' > "$out";;
  marca)   : > "$STUB_MARK";;
  fail)    exit 5;;
  *)       exit 6;;
esac
"""


def _endo_env(tmp_path, mode, extra=None):
    data = tmp_path / "data"
    fixture = _zip_fixture(tmp_path / "endo_fix.zip")
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    _stub(stubdir, "wget", _WGET_STUB)
    env = {"DATA_DIR": str(data), "FIXTURE_ZIP": str(fixture), "ENDO_MODE": mode}
    if extra:
        env.update(extra)
    return data, env, _path_with(stubdir)


def test_endoscapes_sucesso_marca_completo(run, tmp_path):
    data, env, path = _endo_env(tmp_path, "zip")

    rc, status, _ = _call(run, "fetch_endoscapes", env, path)

    assert rc == 0
    assert status == "baixado"
    assert (data / "endoscapes" / ".complete").is_file()
    assert (data / "endoscapes" / "registro.wav").is_file()  # unzip real


def test_endoscapes_zip_invalido_nao_marca_completo(run, tmp_path):
    data, env, path = _endo_env(tmp_path, "invalid")

    rc, status, _ = _call(run, "fetch_endoscapes", env, path)

    assert rc != 0
    assert status == "falhou"
    assert not (data / "endoscapes" / ".complete").exists()


def test_endoscapes_ja_completo_pula_sem_baixar(run, tmp_path):
    data = tmp_path / "data"
    dest = data / "endoscapes"
    dest.mkdir(parents=True)
    (dest / ".complete").touch()
    mark = tmp_path / "STUB_RAN"
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    _stub(stubdir, "wget", _WGET_STUB)
    env = {"DATA_DIR": str(data), "ENDO_MODE": "marca", "STUB_MARK": str(mark)}

    rc, status, _ = _call(run, "fetch_endoscapes", env, _path_with(stubdir))

    assert rc == 0
    assert status == "pulado"
    assert not mark.exists()


# ---------- main: orquestração (URFD/BIDMC) ----------

# Cobre CTU (CTU_DEST) e BIDMC (BIDMC_DEST) — cada fetch exporta só a sua
# variável, então checar qual está setada basta para distinguir os dois.
_PY_OK_MAIN = (
    'if [ -n "${CTU_DEST:-}" ]; then\n'
    '  : > "$CTU_DEST/1001.hea"\n'
    '  : > "$CTU_DEST/1001.dat"\n'
    'elif [ -n "${BIDMC_DEST:-}" ]; then\n'
    '  : > "$BIDMC_DEST/bidmc01.hea"\n'
    '  : > "$BIDMC_DEST/bidmc01.dat"\n'
    '  : > "$BIDMC_DEST/bidmc01n.hea"\n'
    '  : > "$BIDMC_DEST/bidmc01n.dat"\n'
    'fi\n'
)


def _main_setup(tmp_path, dataverse, original, endo):
    data = tmp_path / "data"
    fixture = _zip_fixture(tmp_path / "fix.zip")
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    _stub(stubdir, "curl", _CURL_STUB)
    _stub(stubdir, "wget", _WGET_STUB)
    py = _stub(tmp_path, "py_ok", _PY_OK_MAIN)
    env = {
        "DATA_DIR": str(data),
        "PY": str(py),
        "FIXTURE_ZIP": str(fixture),
        "DATAVERSE_MODE": dataverse,
        "ORIGINAL_MODE": original,
        "ENDO_MODE": endo,
        # Reduzido para o teste de main() ser rápido; a lógica de sentinela
        # por sequência/dataset do URFD já é testada exaustivamente abaixo.
        "URFD_N_FALL": "2",
        "URFD_N_ADL": "2",
    }
    return data, env, _path_with(stubdir)


def test_main_mistura_pula_completos_e_baixa_pendente(run, tmp_path):
    data, env, path = _main_setup(tmp_path, "zip", "fail", "zip")
    for ds in ("ctu-uhb", "icbhi"):
        (data / ds).mkdir(parents=True)
        (data / ds / ".complete").touch()

    r = run('main; echo "RC=$?"', env=env, path=path)

    assert "RC=0" in r.stdout
    assert "CTU-UHB: pulado" in r.stderr
    assert "ICBHI: pulado" in r.stderr
    assert "Endoscapes: baixado" in r.stderr
    assert "URFD: baixado" in r.stderr
    assert "BIDMC: baixado" in r.stderr
    assert (data / "endoscapes" / ".complete").is_file()
    assert (data / "urfd" / ".complete").is_file()
    assert (data / "bidmc" / ".complete").is_file()


def test_main_falha_de_um_nao_derruba_os_outros(run, tmp_path):
    # ICBHI falha nas duas fontes; CTU, Endoscapes, URFD e BIDMC concluem.
    data, env, path = _main_setup(tmp_path, "fail", "fail", "zip")

    r = run('main; echo "RC=$?"', env=env, path=path)

    assert "RC=1" in r.stdout  # exit != 0 porque algo falhou
    assert "CTU-UHB: baixado" in r.stderr
    assert "ICBHI: falhou" in r.stderr
    assert "Endoscapes: baixado" in r.stderr
    assert "URFD: baixado" in r.stderr
    assert "BIDMC: baixado" in r.stderr
    # As demais rodaram apesar de o ICBHI ter falhado antes na sequência
    assert (data / "endoscapes" / ".complete").is_file()
    assert (data / "urfd" / ".complete").is_file()
    assert (data / "bidmc" / ".complete").is_file()
    assert not (data / "icbhi" / ".complete").exists()


def test_main_espaco_conta_urfd_e_bidmc_pendentes(run, tmp_path):
    data, env, path = _main_setup(tmp_path, "zip", "fail", "zip")
    for ds in ("ctu-uhb", "icbhi", "endoscapes"):
        (data / ds).mkdir(parents=True)
        (data / ds / ".complete").touch()
    # Só URFD/BIDMC estão pendentes; uma estimativa absurda para um deles
    # precisa ser o suficiente para abortar — prova que main() soma as duas.
    env["URFD_EST_BYTES"] = "999000000000000"

    r = run('main; echo "RC=$?"', env=env, path=path)

    assert "RC=1" in r.stdout
    assert "insuficiente" in r.stderr


def test_main_ignora_estimativa_de_fonte_ja_completa(run, tmp_path):
    data, env, path = _main_setup(tmp_path, "zip", "fail", "zip")
    for ds in ("ctu-uhb", "icbhi", "endoscapes", "urfd", "bidmc"):
        (data / ds).mkdir(parents=True)
        (data / ds / ".complete").touch()
    # Estimativa absurda, mas a fonte já está completa — não deve contar.
    env["URFD_EST_BYTES"] = "999000000000000"

    r = run('main; echo "RC=$?"', env=env, path=path)

    assert "RC=0" in r.stdout


# ---------- URFD: sentinela por sequência + por dataset ----------

_WGET_URFD_STUB = r"""
out=""; prev=""; url=""
for a in "$@"; do
  [ "$prev" = "-O" ] && out="$a"
  case "$a" in http*) url="$a";; esac
  prev="$a"
done
seq=$(basename "$url" | sed -E 's/-cam0-rgb\.zip$//')
[ -n "${CALL_LOG:-}" ] && echo "$seq" >> "$CALL_LOG"
if [ "$seq" = "${URFD_FAIL_SEQ:-}" ]; then
  exit 9
fi
cp "$FIXTURE_ZIP" "$out"
"""


def _urfd_env(tmp_path, n_fall, n_adl, fail_seq=""):
    data = tmp_path / "data"
    fixture = _zip_fixture(tmp_path / "urfd_fix.zip")
    call_log = tmp_path / "calls.log"
    call_log.write_text("", encoding="utf-8")
    stubdir = tmp_path / "bin"
    stubdir.mkdir()
    _stub(stubdir, "wget", _WGET_URFD_STUB)
    env = {
        "DATA_DIR": str(data),
        "FIXTURE_ZIP": str(fixture),
        "URFD_N_FALL": str(n_fall),
        "URFD_N_ADL": str(n_adl),
        "URFD_FAIL_SEQ": fail_seq,
        "CALL_LOG": str(call_log),
    }
    return data, env, _path_with(stubdir), call_log


def test_urfd_variaveis_do_topo_tem_defaults(run, tmp_path):
    r = run('echo "$URFD_BASE_URL|$URFD_N_FALL|$URFD_N_ADL"')

    assert r.returncode == 0
    assert "fenix.ur.edu.pl" in r.stdout
    assert "30" in r.stdout
    assert "40" in r.stdout


def test_urfd_todas_sequencias_sucesso_marca_completo_de_dataset(run, tmp_path):
    data, env, path, _ = _urfd_env(tmp_path, n_fall=2, n_adl=2)

    rc, status, _ = _call(run, "fetch_urfd", env, path)

    assert rc == 0
    assert status == "baixado"
    assert (data / "urfd" / ".complete").is_file()
    for seq in ("fall-01", "fall-02", "adl-01", "adl-02"):
        assert (data / "urfd" / seq / ".complete").is_file()
        assert (data / "urfd" / seq / "registro.wav").is_file()  # unzip real


def test_urfd_sequencia_falha_nao_marca_completo_de_dataset_mas_demais_completam(
    run, tmp_path
):
    data, env, path, _ = _urfd_env(tmp_path, n_fall=2, n_adl=1, fail_seq="fall-02")

    rc, status, _ = _call(run, "fetch_urfd", env, path)

    assert rc != 0
    assert status == "falhou"
    assert not (data / "urfd" / ".complete").exists()
    # A sequência que falhou não tem sentinela própria...
    assert not (data / "urfd" / "fall-02" / ".complete").exists()
    # ...mas as demais completam normalmente.
    assert (data / "urfd" / "fall-01" / ".complete").is_file()
    assert (data / "urfd" / "adl-01" / ".complete").is_file()


def test_urfd_sequencia_ja_completa_nao_e_rebaixada(run, tmp_path):
    data, env, path, call_log = _urfd_env(tmp_path, n_fall=2, n_adl=1)
    pronta = data / "urfd" / "fall-01"
    pronta.mkdir(parents=True)
    (pronta / ".complete").touch()

    rc, status, _ = _call(run, "fetch_urfd", env, path)

    assert rc == 0
    assert status == "baixado"
    assert "fall-01" not in call_log.read_text(encoding="utf-8").split()
    assert (data / "urfd" / "fall-02" / ".complete").is_file()


# ---------- BIDMC: formas de onda + numerics (achado crítico) ----------

_PY_BIDMC_OK = (
    'test -n "$BIDMC_DEST"\n'
    ': > "$BIDMC_DEST/bidmc01.hea"\n'
    ': > "$BIDMC_DEST/bidmc01.dat"\n'
    ': > "$BIDMC_DEST/bidmc01n.hea"\n'
    ': > "$BIDMC_DEST/bidmc01n.dat"\n'
)
_PY_BIDMC_SO_ONDA = (
    'test -n "$BIDMC_DEST"\n'
    ': > "$BIDMC_DEST/bidmc01.hea"\n'
    ': > "$BIDMC_DEST/bidmc01.dat"\n'
)  # simula o bug real: numerics não veio porque não está no RECORDS
_PY_BIDMC_FALHA = "exit 1\n"


def test_bidmc_sucesso_com_numerics_marca_completo(run, tmp_path):
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_bidmc_ok", _PY_BIDMC_OK)

    rc, status, _ = _call(run, "fetch_bidmc", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc == 0
    assert status == "baixado"
    assert (data / "bidmc" / ".complete").is_file()


def test_bidmc_sem_numerics_nao_marca_completo(run, tmp_path):
    """O achado crítico: só a forma de onda (sem 'n.hea') não é uma aquisição completa —
    é exatamente o que aconteceria se a segunda chamada a dl_database fosse esquecida."""
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_bidmc_so_onda", _PY_BIDMC_SO_ONDA)

    rc, status, _ = _call(run, "fetch_bidmc", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc != 0
    assert status == "falhou"
    assert not (data / "bidmc" / ".complete").exists()


def test_bidmc_python_falha_nao_marca_completo(run, tmp_path):
    data = tmp_path / "data"
    py = _stub(tmp_path, "py_bidmc_falha", _PY_BIDMC_FALHA)

    rc, status, _ = _call(run, "fetch_bidmc", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc != 0
    assert not (data / "bidmc" / ".complete").exists()


def test_bidmc_ja_completo_pula_sem_rodar_python(run, tmp_path):
    data = tmp_path / "data"
    dest = data / "bidmc"
    dest.mkdir(parents=True)
    (dest / ".complete").touch()
    py = _stub(tmp_path, "py_bidmc_marca", ': > "$BIDMC_DEST/STUB_RAN"\n')

    rc, status, _ = _call(run, "fetch_bidmc", {"DATA_DIR": str(data), "PY": str(py)})

    assert rc == 0
    assert status == "pulado"
    assert not (dest / "STUB_RAN").exists()
