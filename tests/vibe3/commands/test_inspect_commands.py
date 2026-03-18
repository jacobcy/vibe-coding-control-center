"""Tests for vibe inspect commands subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_commands_no_args_lists_available():
    """commands 不传参数时列出可用命令，不报错。"""
    result = runner.invoke(app, ["commands"])
    assert result.exit_code == 0
    assert "review" in result.output or "flow" in result.output


def test_inspect_commands_with_command():
    mock_result = MagicMock()
    mock_result.command = "review"
    mock_result.file_path = "src/vibe3/commands/review.py"
    mock_result.call_depth = 2
    mock_result.calls = []
    mock_result.model_dump.return_value = {}
    with patch(
        "vibe3.commands.inspect.command_analyzer.analyze_command",
        return_value=mock_result,
    ):
        result = runner.invoke(app, ["commands", "review"])
    assert result.exit_code == 0
