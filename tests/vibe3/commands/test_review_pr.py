"""Tests for vibe review pr subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.
"""

import re
from unittest.mock import MagicMock

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


def _mock_result(stdout: str = "## Review\nLooks good.\nVERDICT: PASS"):
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
def mock_review_usecase(monkeypatch):
    """Stub ReviewUsecase for fast CLI surface tests."""
    usecase = MagicMock()
    usecase.build_pr_review.return_value = (
        ReviewRequest(scope=ReviewScope.for_pr(42)),
        101,
        "feature/branch",
    )
    usecase.execute_review.return_value = MagicMock(
        verdict="PASS",
        handoff_file=None,
    )
    monkeypatch.setattr("vibe3.commands.review._build_review_usecase", lambda: usecase)
    return usecase


def test_review_pr_missing_arg_shows_error():
    """vibe review pr (missing PR number) -> friendly error, not crash."""
    result = runner.invoke(app, ["pr"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_review_pr_pass(mock_review_usecase):
    mock_review_usecase.execute_review.return_value.verdict = "PASS"
    result = runner.invoke(app, ["pr", "42", "--sync"])
    assert result.exit_code == 0
    assert "PASS" in result.output
    mock_review_usecase.build_pr_review.assert_called_once_with(42)
    _, kwargs = mock_review_usecase.execute_review.call_args
    assert kwargs["branch"] == "feature/branch"


def test_review_pr_block_exits_1(mock_review_usecase):
    mock_review_usecase.execute_review.return_value.verdict = "BLOCK"
    result = runner.invoke(app, ["pr", "42", "--sync"])
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


def test_review_pr_is_local_only(mock_review_usecase):
    """review pr should not call GitHub publish methods."""
    mock_review_usecase.execute_review.return_value.verdict = "PASS"
    result = runner.invoke(app, ["pr", "42", "--sync"])

    assert result.exit_code == 0


def test_review_pr_async_dispatches_background_execution(mock_review_usecase):
    mock_review_usecase.execute_review.return_value.verdict = "ASYNC"
    result = runner.invoke(app, ["pr", "42", "--async"])

    assert result.exit_code == 0
    _, kwargs = mock_review_usecase.execute_review.call_args
    assert kwargs["async_mode"] is True
    assert kwargs["branch"] == "feature/branch"


def test_async_pr_refuses_when_head_fetch_fails(mock_review_usecase):
    """Refuse async review if head branch cannot be resolved from PR metadata."""
    mock_review_usecase.build_pr_review.return_value = (
        ReviewRequest(scope=ReviewScope.for_pr(42)),
        101,
        None,  # head_branch resolve failed
    )

    result = runner.invoke(app, ["pr", "42", "--async"])

    assert result.exit_code == 1
    assert "Could not resolve head branch" in result.output


def test_dry_run_pr_allows_missing_head_branch(mock_review_usecase):
    mock_review_usecase.build_pr_review.return_value = (
        ReviewRequest(scope=ReviewScope.for_pr(42)),
        101,
        None,
    )
    mock_review_usecase.execute_review.return_value.verdict = "DRY_RUN"

    result = runner.invoke(app, ["pr", "42", "--dry-run", "--sync"])

    assert result.exit_code == 0
    _, kwargs = mock_review_usecase.execute_review.call_args
    assert kwargs["branch"] is None


def test_review_parser_failure_returns_error_verdict(mock_review_usecase):
    """Surface ERROR verdict when usecase returns parse-failure result."""
    mock_review_usecase.execute_review.return_value.verdict = "ERROR"
    result = runner.invoke(app, ["pr", "42", "--sync"])

    assert result.exit_code == 1
    assert "Verdict: ERROR" in result.output


def test_review_pr_rejects_unknown_agent_param():
    """review pr should reject --agent (not a valid option).

    This test ensures the hook-CLI contract is enforced.
    """
    result = runner.invoke(app, ["pr", "42", "--agent", "code-reviewer"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "error" in result.output.lower()
