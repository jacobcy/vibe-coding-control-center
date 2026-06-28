"""Tests for vibe inspect CLI surface.

Merged from:
- test_inspect_help.py (2 tests)
- test_inspect_commands.py (2 tests)
- test_issue_337_fix.py (3 tests)

Tests CLI surface: argument validation, help output, exit codes, format options.
All external services are mocked.
"""

import json
from unittest.mock import MagicMock, patch

# ========== Help Tests (from test_inspect_help.py) ==========


def test_inspect_no_args_shows_help(cli_runner, inspect_app_fixture):
    """vibe inspect (no subcommand) shows help."""
    result = cli_runner.invoke(inspect_app_fixture, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "inspect" in result.output.lower()


def test_inspect_help_flag(cli_runner, inspect_app_fixture):
    result = cli_runner.invoke(inspect_app_fixture, ["--help"])
    assert result.exit_code == 0
    assert "metrics" not in result.output
    assert "dead-code" in result.output
    assert "pr" not in result.output


# ========== Commands Tests (from test_inspect_commands.py) ==========


def test_inspect_commands_no_args_lists_available(cli_runner, inspect_app_fixture):
    """commands 不传参数时列出可分析的顶层命令，不报错。"""
    result = cli_runner.invoke(inspect_app_fixture, ["commands"])
    assert result.exit_code == 0
    assert "=== vibe3 command structure ===" in result.output
    assert "Top-level commands:" in result.output
    assert "flow" in result.output
    assert "pr" in result.output
    assert "review" in result.output
    assert "inspect" in result.output
    assert "symbols" not in result.output
    assert "files" not in result.output


def test_inspect_commands_with_command(cli_runner, inspect_app_fixture):
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
        result = cli_runner.invoke(inspect_app_fixture, ["commands", "review"])
    assert result.exit_code == 0


# ========== Issue #337 Format Options Tests (from test_issue_337_fix.py) ==========


def test_inspect_commands_json_no_command(cli_runner, inspect_app_fixture):
    """Verify that --json works even when no command is specified."""
    result = cli_runner.invoke(inspect_app_fixture, ["commands", "--json"])
    assert result.exit_code == 0
    # Output should be valid JSON and contain top-level commands
    data = json.loads(result.output)
    assert data["command"] == "vibe"
    assert any(node["name"] == "flow" for node in data["call_tree"])
    assert any(node["name"] == "pr" for node in data["call_tree"])


def test_inspect_commands_tree_no_command(cli_runner, inspect_app_fixture):
    """Verify that --tree works even when no command is specified."""
    result = cli_runner.invoke(inspect_app_fixture, ["commands", "--tree"])
    assert result.exit_code == 0
    assert "vibe (src/vibe3/cli.py:0)" in result.output
    assert "├─ flow (L0)" in result.output
    assert "├─ pr (L0)" in result.output


def test_inspect_commands_default_no_command(cli_runner, inspect_app_fixture):
    """Verify that no flags still results in plain text output."""
    result = cli_runner.invoke(inspect_app_fixture, ["commands"])
    assert result.exit_code == 0
    assert "=== vibe3 command structure ===" in result.output
    assert "Top-level commands:" in result.output
    assert "flow" in result.output
    assert "pr" in result.output
