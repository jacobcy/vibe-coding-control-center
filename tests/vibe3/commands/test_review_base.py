"""Tests for vibe review base subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


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


def _patch_review_base_usecase(monkeypatch, verdict: str = "PASS"):
    mock_usecase = MagicMock()
    mock_usecase.build_base_review.return_value = (
        MagicMock(),
        101,
    )
    mock_usecase.execute_review.return_value = MagicMock(
        verdict=verdict,
        handoff_file=None,
    )
    monkeypatch.setattr(
        "vibe3.commands.review._build_review_usecase",
        lambda flow_service=None: mock_usecase,
    )
    return mock_usecase


def test_review_base_defaults_to_origin_main(monkeypatch):
    """Test that review base works with AST analysis."""
    mock_usecase = _patch_review_base_usecase(monkeypatch)
    with (
        patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_review_base",
            return_value=MagicMock(base_branch="origin/main", auto_detected=True),
        ),
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
    ):
        result = runner.invoke(app, ["base", "--sync"])
    assert result.exit_code == 0
    mock_usecase.execute_review.assert_called_once()


def test_review_base_pass(monkeypatch):
    mock_usecase = _patch_review_base_usecase(monkeypatch)
    with (
        patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_review_base",
            return_value=MagicMock(base_branch="origin/develop", auto_detected=False),
        ),
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
    ):
        result = runner.invoke(app, ["base", "origin/develop", "--sync"])
    assert result.exit_code == 0
    mock_usecase.execute_review.assert_called_once()


def test_review_base_uses_shared_resolution_when_base_omitted(monkeypatch):
    """Review base should delegate omitted base handling to the shared resolver."""
    _patch_review_base_usecase(monkeypatch)
    with (
        patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_review_base",
            return_value=MagicMock(base_branch="origin/main", auto_detected=True),
        ) as mock_resolve,
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
    ):
        result = runner.invoke(app, ["base", "--sync"])

    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(None, current_branch="feature/test")


def test_review_base_does_not_have_publish_option():
    """review base should NOT have --publish option."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    assert "--publish" not in result.output


def test_review_base_rejects_unknown_agent_param():
    """review base should reject --agent (not a valid option).

    This test ensures the hook-CLI contract is enforced: pre-push.sh
    should not use --agent parameter.
    """
    result = runner.invoke(app, ["base", "--agent", "code-reviewer"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "error" in result.output.lower()


def test_review_base_async_skips_parent_inspect_precompute():
    """Test that review base --async now goes through usecase layer.

    Note: After refactoring, async mode is handled in usecase layer,
    so inspect/snapshot WILL be called in the parent process.
    The optimization was removed for architectural consistency.
    """
    mock_usecase = MagicMock()
    mock_usecase.build_base_review.return_value = (MagicMock(), 101)
    mock_usecase.execute_review.return_value = MagicMock(
        verdict="ASYNC",
        handoff_file=None,
    )

    with (
        patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_review_base",
            return_value=MagicMock(base_branch="origin/main", auto_detected=False),
        ),
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
        patch(
            "vibe3.commands.review._build_review_usecase",
            return_value=mock_usecase,
        ),
    ):
        result = runner.invoke(app, ["base", "--async"])

    assert result.exit_code == 0
    # After refactoring, execute_review is called with async_mode=True
    mock_usecase.execute_review.assert_called_once()
