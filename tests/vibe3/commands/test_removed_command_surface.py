"""Regression tests for removed command surface.

These tests ensure that deprecated or removed commands do not accidentally
reappear in the CLI surface. All tests use CliRunner for speed.
"""

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_vibe3_hooks_command_removed() -> None:
    result = runner.invoke(app, ["hooks"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_pr_draft_command_removed() -> None:
    """pr draft should be removed; pr create handles draft creation."""
    result = runner.invoke(app, ["pr", "draft", "--help"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_pr_merge_command_removed() -> None:
    """pr merge should be removed; flow done / integrate handles merging."""
    result = runner.invoke(app, ["pr", "merge", "--help"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_gate_command_removed() -> None:
    """review-gate should not be part of the public top-level CLI surface."""
    result = runner.invoke(app, ["review-gate", "--help"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_task_command_removed() -> None:
    """task should not be part of the public top-level CLI surface."""
    result = runner.invoke(app, ["task", "--help"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )
