"""Guarda: nenhum módulo fora de aws/clients.py chama
`boto3.client(...)` diretamente. Testes ficam de fora da varredura — podem
precisar de um cliente cru para verificação independente do factory.
"""

import re
from pathlib import Path

_PATTERN = re.compile(r"boto3\.client\(")


def find_boto3_client_violations(
    root: Path, exclude: set[Path], skip_dir_names: frozenset[str] = frozenset()
) -> list[str]:
    """Varre `root` por `.py` chamando `boto3.client(` fora de `exclude`/`skip_dir_names`."""
    violations = []
    for path in sorted(root.rglob("*.py")):
        if skip_dir_names & set(path.relative_to(root).parts[:-1]):
            continue
        if path.resolve() in exclude:
            continue
        if _PATTERN.search(path.read_text(encoding="utf-8")):
            violations.append(str(path))
    return violations


def test_repo_atual_nao_tem_boto3_client_direto():
    backend = Path(__file__).resolve().parents[2]  # backend/
    exclude = {(backend / "aws" / "clients.py").resolve()}

    violations = find_boto3_client_violations(backend, exclude, skip_dir_names=frozenset({"tests"}))

    assert violations == [], f"boto3.client(...) direto fora do factory: {violations}"


def test_guarda_detecta_violacao_injetada(tmp_path):
    (tmp_path / "modulo_ok.py").write_text(
        "from aws.clients import get_client\nc = get_client('s3')\n", encoding="utf-8"
    )
    violador = tmp_path / "modulo_com_violacao.py"
    violador.write_text("import boto3\nc = boto3.client('s3')\n", encoding="utf-8")

    violations = find_boto3_client_violations(tmp_path, exclude=set())

    assert violations == [str(violador)]


def test_guarda_nao_acusa_arquivo_excluido():
    backend = Path(__file__).resolve().parents[2]
    clients_py = (backend / "aws" / "clients.py").resolve()

    violations = find_boto3_client_violations(
        backend, exclude={clients_py}, skip_dir_names=frozenset({"tests"})
    )

    assert str(clients_py) not in violations


def test_guarda_ignora_diretorio_tests(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_algo.py").write_text(
        "import boto3\nc = boto3.client('s3')  # verificação independente\n",
        encoding="utf-8",
    )

    violations = find_boto3_client_violations(
        tmp_path, exclude=set(), skip_dir_names=frozenset({"tests"})
    )

    assert violations == []
