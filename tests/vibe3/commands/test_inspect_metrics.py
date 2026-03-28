"""Tests for removed vibe inspect metrics subcommand."""

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_metrics_no_longer_exists():
    """metrics subcommand should be removed from inspect surface."""
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_inspect_help_hides_metrics():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "metrics" not in result.output
