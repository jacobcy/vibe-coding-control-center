"""Tests for vibe inspect structure subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_structure_result():
    m = MagicMock()
    m.language = "python"
    m.total_loc = 80
    m.function_count = 3
    m.functions = []
    m.model_dump.return_value = {
        "path": "src/vibe3/cli.py",
        "total_loc": 80,
        "function_count": 3,
    }
    return m


def test_inspect_structure_no_args_scans_all():
    """structure 不传文件时扫描整个 src/vibe3，不应报错。"""
    mock_result = _mock_structure_result()
    with patch(
        "vibe3.commands.inspect.structure_service.analyze_python_file",
        return_value=mock_result,
    ):
        result = runner.invoke(app, ["structure"])
    assert result.exit_code == 0


def test_inspect_structure_with_file():
    mock_result = _mock_structure_result()
    with patch(
        "vibe3.commands.inspect.structure_service.analyze_file",
        return_value=mock_result,
    ):
        result = runner.invoke(app, ["structure", "src/vibe3/cli.py"])
    assert result.exit_code == 0
    assert "Structure" in result.output


def test_inspect_structure_help():
    result = runner.invoke(app, ["structure", "--help"])
    assert result.exit_code == 0
