"""Tests for vibe review general help and no-args behavior.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.

Note: This file only contains general help tests. Subcommand tests are split into:
- test_review_pr.py
- test_review_base.py
"""

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def test_review_no_args_shows_help():
    """vibe review (no subcommand) -> shows help (exit 0 or 2 per typer no_args_is_help)."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "pr" in result.output


def test_review_help_only_shows_supported_commands():
    """vibe review --help should only show supported commands: base, pr.

    Removed commands: commit, uncommitted, analyze-commit
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Supported commands
    assert "base" in result.output
    assert "pr" in result.output
    # Removed commands - should NOT appear
    assert "commit" not in result.output.lower()
    assert "uncommitted" not in result.output.lower()
    assert "analyze-commit" not in result.output.lower()


def test_review_commit_command_removed():
    """vibe review commit -> should fail (command removed)."""
    result = runner.invoke(app, ["commit", "HEAD"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_uncommitted_command_removed():
    """vibe review uncommitted -> should fail (command removed)."""
    result = runner.invoke(app, ["uncommitted"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_analyze_commit_command_removed():
    """vibe review analyze-commit -> should fail (command removed)."""
    result = runner.invoke(app, ["analyze-commit", "HEAD"])
    assert result.exit_code != 0
    assert (
        "no such command" in result.output.lower() or "error" in result.output.lower()
    )


def test_review_base_help_mentions_agent_and_model_options():
    """vibe review base --help should mention --agent and --model options."""
    # Disable color codes in output
    result = runner.invoke(app, ["base", "--help"], env={"NO_COLOR": "1"})
    assert result.exit_code == 0
    assert "--agent" in result.output
    assert "--model" in result.output


def test_review_pr_help_mentions_agent_and_model_options():
    """vibe review pr --help should mention --agent and --model options."""
    # Disable color codes in output
    result = runner.invoke(app, ["pr", "--help"], env={"NO_COLOR": "1"})
    assert result.exit_code == 0
    assert "--agent" in result.output
    assert "--model" in result.output
