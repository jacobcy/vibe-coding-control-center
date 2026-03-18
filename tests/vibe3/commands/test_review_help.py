"""Tests for vibe review general help and no-args behavior.

Tests CLI surface: argument validation, help output, exit codes.
All external services (Codex, GitHub, Git) are mocked.

Note: This file only contains general help tests. Subcommand tests are split into:
- test_review_pr.py
- test_review_commit.py
- test_review_base.py
- test_review_uncommitted.py
- test_review_analyze_commit.py
"""

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def test_review_no_args_shows_help():
    """vibe review (无子命令) → shows help (exit 0 or 2 per typer no_args_is_help)."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "pr" in result.output


def test_review_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pr" in result.output
    assert "commit" in result.output
    assert "uncommitted" in result.output