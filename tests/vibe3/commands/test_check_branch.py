"""Tests for vibe3 check --branch parameter."""

from typer.testing import CliRunner

from vibe3.commands.check import app

runner = CliRunner()


def test_check_branch_mutually_exclusive_with_init() -> None:
    """--branch and --init should be mutually exclusive."""
    result = runner.invoke(app, ["--branch", "dev/test", "--init"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_check_branch_mutually_exclusive_with_clean_branch() -> None:
    """--branch and --clean-branch should be mutually exclusive."""
    result = runner.invoke(app, ["--branch", "dev/test", "--clean-branch"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()
