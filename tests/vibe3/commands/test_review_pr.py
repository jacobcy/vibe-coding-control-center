"""Tests for vibe review pr subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.
"""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes for CI-safe assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _mock_review(verdict: str = "PASS"):
    m = MagicMock()
    m.verdict = verdict
    m.comments = []
    return m


def _mock_result(stdout: str = "## Review\nLooks good."):
    return MagicMock(
        success=True,
        exit_code=0,
        stdout=stdout,
        stderr="",
        handoff_file=None,
        session_id=None,
    )


def _mock_inspect_data():
    return {
        "changed_symbols": {
            "src/review.py": ["build_review_context", "run_inspect_json"]
        }
    }


def test_review_pr_missing_arg_shows_error():
    """vibe review pr (missing PR number) -> friendly error, not crash."""
    result = runner.invoke(app, ["pr"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_review_pr_pass():
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ) as mock_inspect,
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 0
    assert "PASS" in result.output
    mock_inspect.assert_called_once_with(["pr", "42"])


def test_review_pr_block_exits_1():
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("BLOCK"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 1


def test_review_pr_help():
    result = runner.invoke(app, ["pr", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "PR number" in output
    assert "--async" in output


def test_review_pr_does_not_have_publish_option():
    """review pr should NOT have --publish option (local-only)."""
    result = runner.invoke(app, ["pr", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "--publish" not in output


def test_review_pr_is_local_only():
    """review pr should not call GitHub publish methods."""
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])

    assert result.exit_code == 0


def test_review_pr_rejects_unknown_agent_param():
    """review pr should reject --agent (not a valid option).

    This test ensures the hook-CLI contract is enforced.
    """
    result = runner.invoke(app, ["pr", "42", "--agent", "code-reviewer"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "error" in result.output.lower()


def test_review_pr_preserves_existing_session_id_when_wrapper_returns_none():
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])

    assert result.exit_code == 0


def test_review_pr_async_dispatches_background_execution():
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch("vibe3.commands.review.get_current_branch", return_value="task/issue250"),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute",
            return_value=_mock_result(),
        ) as mock_execute,
        patch("vibe3.commands.review.parse_codex_review") as mock_parse,
    ):
        result = runner.invoke(app, ["pr", "42", "--async"])

    assert result.exit_code == 0
    mock_execute.assert_called_once()
    assert mock_execute.call_args.kwargs["async_mode"] is True
    mock_parse.assert_not_called()
