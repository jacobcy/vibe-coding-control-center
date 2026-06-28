"""Contract tests for single-file Python AST evidence."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from vibe3.analysis.python_file_inspector import inspect_python_file


def test_inspects_qualified_declarations_and_direct_imports(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    content = (
        "import os as operating_system\n"
        "from .ports import Port as P\n\n"
        "class Worker:\n"
        "    async def run(self):\n"
        "        def nested():\n"
        "            return 1\n"
        "        return nested()\n"
    )
    source.write_text(content, encoding="utf-8")

    result = inspect_python_file(source, repo_root=tmp_path)

    assert result.status == "ready"
    assert result.file is not None
    assert result.file.path == "sample.py"
    assert result.file.content_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert [declaration.qualified_name for declaration in result.declarations] == [
        "Worker",
        "Worker.run",
        "Worker.run.nested",
    ]
    assert [declaration.kind for declaration in result.declarations] == [
        "class",
        "async_method",
        "nested_function",
    ]
    assert result.declarations[1].range.start_line == 5
    assert result.declarations[1].range.end_line == 8
    assert result.imports[0].module == "os"
    assert result.imports[0].aliases == {"os": "operating_system"}
    assert result.imports[1].module == "ports"
    assert result.imports[1].names == ["Port"]
    assert result.imports[1].aliases == {"Port": "P"}
    assert result.imports[1].level == 1


def test_ranges_match_python_ast(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def first():\n    return 1\n", encoding="utf-8")
    expected = ast.parse(source.read_text(encoding="utf-8")).body[0]

    result = inspect_python_file(source, repo_root=tmp_path)

    assert result.declarations[0].range.start_line == expected.lineno
    assert result.declarations[0].range.end_line == expected.end_lineno


def test_syntax_error_is_structured(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("def broken(:\n", encoding="utf-8")

    result = inspect_python_file(source, repo_root=tmp_path)

    assert result.status == "error"
    assert result.diagnostics[0].code == "syntax_error"
    assert result.diagnostics[0].range is not None
    assert result.diagnostics[0].range.start_line == 1


def test_directory_and_non_python_are_unsupported(tmp_path: Path) -> None:
    shell = tmp_path / "script.sh"
    shell.write_text("run() { :; }\n", encoding="utf-8")

    directory_result = inspect_python_file(tmp_path, repo_root=tmp_path)
    shell_result = inspect_python_file(shell, repo_root=tmp_path)

    assert directory_result.status == "unsupported"
    assert directory_result.diagnostics[0].code == "directory_not_supported"
    assert shell_result.status == "unsupported"
    assert shell_result.diagnostics[0].code == "unsupported_file_type"


def test_missing_file_is_error(tmp_path: Path) -> None:
    result = inspect_python_file(tmp_path / "missing.py", repo_root=tmp_path)

    assert result.status == "error"
    assert result.diagnostics[0].code == "file_not_found"
