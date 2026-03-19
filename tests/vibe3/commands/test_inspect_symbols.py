"""Tests for vibe inspect symbols subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_symbols_no_args_uses_dot():
    """symbols 不传参数时应提示错误。"""
    mock_svc = MagicMock()
    mock_svc.analyze_file.return_value = {"status": "ok", "symbols": []}
    with patch("vibe3.commands.inspect_symbols.SerenaService", return_value=mock_svc):
        result = runner.invoke(app, ["symbols"])
    assert result.exit_code != 0
    assert "Please provide a symbol specification" in result.output


def test_inspect_symbols_with_file():
    mock_svc = MagicMock()
    mock_svc.analyze_file.return_value = {
        "file": "src/vibe3/cli.py",
        "symbols": [{"name": "my_func", "references": 2, "type": "function"}],
    }
    with patch("vibe3.commands.inspect_symbols.SerenaService", return_value=mock_svc):
        result = runner.invoke(app, ["symbols", "src/vibe3/cli.py"])
    assert result.exit_code == 0
    assert "my_func" in result.output


def test_inspect_symbols_json():
    mock_svc = MagicMock()
    mock_svc.analyze_file.return_value = {
        "file": "src/vibe3/cli.py",
        "symbols": [],
    }
    with patch("vibe3.commands.inspect_symbols.SerenaService", return_value=mock_svc):
        result = runner.invoke(app, ["symbols", "src/vibe3/cli.py", "--json"])
    assert result.exit_code == 0
