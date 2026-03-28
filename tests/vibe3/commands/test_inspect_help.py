"""Tests for vibe inspect general help and no-args behavior.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.

Note: This file only contains general help tests. Subcommand tests are split into:
- test_inspect_metrics.py
- test_inspect_structure.py
- test_inspect_symbols.py
- test_inspect_commands.py
- test_inspect_change_analysis.py
"""

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_no_args_shows_help():
    """vibe inspect (no subcommand) shows help."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "inspect" in result.output.lower()


def test_inspect_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "metrics" not in result.output
    assert "uncommit" in result.output
    assert "pr" in result.output
