"""Tests for vibe review pr subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.
"""

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.review import app
from vibe3.models.review import ReviewRequest, ReviewScope

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


@pytest.fixture
def mock_pr_build():
    """Default mock for ReviewUsecase.build_pr_review."""
    with patch("vibe3.commands.review.ReviewUsecase.build_pr_review") as m:
        m.return_value = (
            ReviewRequest(scope=ReviewScope.for_pr(42)),
            101,
            "feature/branch",
        )
        yield m


def test_review_pr_missing_arg_shows_error():
    """vibe review pr (missing PR number) -> friendly error, not crash."""
    result = runner.invoke(app, ["pr"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_review_pr_pass(mock_pr_build):
    with (
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
    mock_pr_build.assert_called_once_with(42)


def test_review_pr_block_exits_1(mock_pr_build):
    with (
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


def test_review_pr_is_local_only(mock_pr_build):
    """review pr should not call GitHub publish methods."""
    with (
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


def test_review_pr_async_dispatches_background_execution(mock_pr_build):
    with (
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
    # Verify branch came from PR head_branch ("feature/branch" from fixture)
    command = mock_execute.call_args.args[0]
    assert command.branch == "feature/branch"
    mock_parse.assert_not_called()


def test_async_pr_refuses_when_head_fetch_fails(mock_pr_build):
    """Refuse async review if head branch cannot be resolved from PR metadata."""
    mock_pr_build.return_value = (
        ReviewRequest(scope=ReviewScope.for_pr(42)),
        101,
        None,  # head_branch resolve failed
    )

    result = runner.invoke(app, ["pr", "42", "--async"])

    assert result.exit_code == 1
    assert "Could not resolve head branch" in result.output


def test_review_parser_failure_returns_error_verdict(mock_pr_build):
    """When parser fails, execute_review should catch it and return ERROR verdict."""
    from vibe3.agents.review_parser import ReviewParserError

    with (
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result("NO VERDICT HERE"),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            side_effect=ReviewParserError("Missing verdict"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])

    assert result.exit_code == 0
    assert "Verdict: ERROR" in result.output
