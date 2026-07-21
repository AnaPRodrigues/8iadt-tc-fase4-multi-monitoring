"""Testes de verify_zip (DATA-09, DATA-13) — a defesa contra o 403/HTML disfarçado."""

import os
import zipfile


def _zip_real(path, payload_bytes=5000):
    """Zip com uma entrada real → começa com PK\\x03\\x04 e passa do tamanho mínimo."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("dado.bin", os.urandom(payload_bytes))  # incompressível: mantém tamanho
    return path


def test_zip_real_e_aceito(run, tmp_path):
    z = _zip_real(tmp_path / "ok.zip")

    r = run(f"verify_zip '{z}'")

    assert r.returncode == 0


def test_pagina_html_de_erro_e_rejeitada(run, tmp_path):
    """O caso real do ICBHI: 41 KB de HTML servidos como .zip com HTTP 200."""
    p = tmp_path / "erro.zip"
    p.write_text("<!DOCTYPE html>\n<html><head><title>403</title></head>" + "x" * 2000)

    r = run(f"verify_zip '{p}'")

    assert r.returncode != 0
    assert "não é um zip" in r.stderr or "nao e um zip" in r.stderr


def test_arquivo_vazio_e_rejeitado(run, tmp_path):
    p = tmp_path / "vazio.zip"
    p.write_bytes(b"")

    r = run(f"verify_zip '{p}'")

    assert r.returncode != 0
    assert "pequeno" in r.stderr


def test_arquivo_pequeno_nao_zip_e_rejeitado(run, tmp_path):
    p = tmp_path / "lixo.zip"
    p.write_bytes(b"notazip")

    r = run(f"verify_zip '{p}'")

    assert r.returncode != 0


def test_arquivo_inexistente_e_rejeitado(run, tmp_path):
    r = run(f"verify_zip '{tmp_path / 'nao-existe.zip'}'")

    assert r.returncode != 0
    assert "inexistente" in r.stderr


def test_zip_valido_mas_abaixo_do_minimo_e_rejeitado(run, tmp_path):
    """Um zip real porém minúsculo (< MIN_ZIP_BYTES) não é um dataset."""
    z = _zip_real(tmp_path / "mini.zip", payload_bytes=10)

    r = run(f"verify_zip '{z}'", env={"MIN_ZIP_BYTES": "1000000"})

    assert r.returncode != 0
    assert "pequeno" in r.stderr
