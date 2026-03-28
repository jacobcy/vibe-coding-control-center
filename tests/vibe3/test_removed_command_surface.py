"""Regression tests for removed command surface."""

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_vibe3_hooks_command_removed() -> None:
    result = runner.invoke(app, ["hooks"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_vibe3_inspect_metrics_command_removed() -> None:
    result = runner.invoke(app, ["inspect", "metrics"])
    assert result.exit_code != 0
    assert "No such command" in result.output
