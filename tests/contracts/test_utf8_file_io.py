import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FILES = [
    "lib/checkpoint.py",
    "lib/pipeline_loader.py",
    "schemas/artifacts/__init__.py",
    "styles/playbook_loader.py",
]


@pytest.mark.parametrize("relative_path", RUNTIME_FILES)
def test_pipeline_contract_files_use_explicit_utf8(relative_path: str) -> None:
    path = REPO_ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    bare_opens = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "open":
            continue
        if not any(keyword.arg == "encoding" for keyword in node.keywords):
            bare_opens.append(node.lineno)

    assert bare_opens == [], f"bare open() calls at lines {bare_opens}"
