"""Regression tests for removed command surface.

Merged from test_removed_command_surface.py + removal tests from test_review_help.py.
These tests ensure that deprecated or removed commands do not accidentally
reappear in the CLI surface. All tests use CliRunner for speed.
"""

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.review import app as review_app

runner = CliRunner()


# ==============================================================================
# Top-level removed commands (from test_removed_command_surface.py)
# ==============================================================================


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


# ==============================================================================
# Review subcommand removal tests (from test_review_help.py)
# ==============================================================================


def test_review_commit_command_removed():
    """vibe review commit -> should fail (command removed)."""
    result = runner.invoke(review_app, ["commit", "HEAD"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_uncommitted_command_removed():
    """vibe review uncommitted -> should fail (command removed)."""
    result = runner.invoke(review_app, ["uncommitted"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_analyze_commit_command_removed():
    """vibe review analyze-commit -> should fail (command removed)."""
    result = runner.invoke(review_app, ["analyze-commit", "HEAD"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )
