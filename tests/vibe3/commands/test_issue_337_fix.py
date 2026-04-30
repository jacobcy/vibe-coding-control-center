"""Tests for issue #337: inspect commands format options support.

Verify formatting flags when no command is specified.
"""

import json

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_commands_json_no_command():
    """Verify that --json works even when no command is specified."""
    result = runner.invoke(app, ["commands", "--json"])
    assert result.exit_code == 0
    # Output should be valid JSON and contain top-level commands
    data = json.loads(result.output)
    assert data["command"] == "vibe"
    assert any(node["name"] == "flow" for node in data["call_tree"])
    assert any(node["name"] == "pr" for node in data["call_tree"])


def test_inspect_commands_tree_no_command():
    """Verify that --tree works even when no command is specified."""
    result = runner.invoke(app, ["commands", "--tree"])
    assert result.exit_code == 0
    assert "vibe (src/vibe3/cli.py:0)" in result.output
    assert "├─ flow (L0)" in result.output
    assert "├─ pr (L0)" in result.output


def test_inspect_commands_default_no_command():
    """Verify that no flags still result in plain text output."""
    result = runner.invoke(app, ["commands"])
    assert result.exit_code == 0
    assert "=== vibe3 command structure ===" in result.output
    assert "Top-level commands:" in result.output
    assert "flow" in result.output
    assert "pr" in result.output
