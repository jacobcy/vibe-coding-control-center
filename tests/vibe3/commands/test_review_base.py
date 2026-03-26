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


def test_review_base_defaults_to_origin_main():
    """Test that review base works with AST analysis."""
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
        patch(
            "vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"
        ),
        patch(
            "vibe3.utils.branch_utils.find_parent_branch",
            return_value="origin/main",
        ),
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
    ):
        result = runner.invoke(app, ["base"])
        assert result.exit_code == 0


def test_review_base_pass():
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.CodeagentExecutionService.execute_sync",
            return_value=_mock_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
        patch(
            "vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"
        ),
        patch(
            "vibe3.commands.review.ensure_flow_for_current_branch",
            return_value=(MagicMock(), "feature/test"),
        ),
    ):
        result = runner.invoke(app, ["base", "origin/develop"])
    assert result.exit_code == 0


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
