from __future__ import annotations

import ast
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "onpe_mcp"
ALLOWED_SQLITE_FILES = {"storage.py", "analytics.py"}


def _uses_sqlite_connect(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "sqlite3"
            and func.attr == "connect"
        ):
            return True
    return False


def _imports_sqlite(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "sqlite3" for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
            return True
    return False


def test_sqlite_usage_stays_in_data_layer() -> None:
    offenders: list[str] = []

    for py_file in sorted(SRC_ROOT.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(py_file))

        if py_file.name in ALLOWED_SQLITE_FILES:
            continue

        if _imports_sqlite(tree) or _uses_sqlite_connect(tree):
            offenders.append(py_file.name)

    assert not offenders, (
        "Direct sqlite usage is restricted to storage/analytics layer only. "
        f"Move DB access behind MCP tools/storage APIs. Offenders: {offenders}"
    )
