"""StructureService 单元测试."""

import pytest

from vibe3.services.structure_service import (
    StructureError,
    analyze_file,
    analyze_python_file,
    analyze_shell_file,
)

PYTHON_SOURCE = """\
def hello(name: str) -> str:
    return f"Hello {name}"

async def world() -> None:
    pass
"""

SHELL_SOURCE = """\
#!/usr/bin/env zsh
function setup() {
    echo "setup"
}
teardown() {
    echo "teardown"
}
"""


class TestAnalyzePythonFile:
    """analyze_python_file 测试."""

    def test_extracts_functions(self, tmp_path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(PYTHON_SOURCE)

        result = analyze_python_file(str(f))

        assert result.language == "python"
        assert result.function_count == 2
        names = [fn.name for fn in result.functions]
        assert "hello" in names
        assert "world" in names

    def test_counts_loc(self, tmp_path) -> None:
        f = tmp_path / "sample.py"
        f.write_text(PYTHON_SOURCE)

        result = analyze_python_file(str(f))

        assert result.total_loc == len(PYTHON_SOURCE.splitlines())

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(StructureError, match="not found"):
            analyze_python_file("/nonexistent/file.py")

    def test_raises_on_syntax_error(self, tmp_path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n    pass")

        with pytest.raises(StructureError, match="Syntax error"):
            analyze_python_file(str(f))


class TestAnalyzeShellFile:
    """analyze_shell_file 测试."""

    def test_extracts_functions(self, tmp_path) -> None:
        f = tmp_path / "sample.sh"
        f.write_text(SHELL_SOURCE)

        result = analyze_shell_file(str(f))

        assert result.language == "shell"
        assert result.function_count == 2
        names = [fn.name for fn in result.functions]
        assert "setup" in names
        assert "teardown" in names

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(StructureError, match="not found"):
            analyze_shell_file("/nonexistent/file.sh")


class TestAnalyzeFile:
    """analyze_file 自动分发测试."""

    def test_dispatches_python(self, tmp_path) -> None:
        f = tmp_path / "foo.py"
        f.write_text("x = 1\n")
        result = analyze_file(str(f))
        assert result.language == "python"

    def test_dispatches_shell(self, tmp_path) -> None:
        f = tmp_path / "foo.sh"
        f.write_text("echo hi\n")
        result = analyze_file(str(f))
        assert result.language == "shell"

    def test_raises_on_unsupported(self, tmp_path) -> None:
        f = tmp_path / "foo.rb"
        f.write_text("puts 'hi'\n")
        with pytest.raises(StructureError, match="Unsupported"):
            analyze_file(str(f))
