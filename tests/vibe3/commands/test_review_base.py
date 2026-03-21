"""Tests for vibe review base subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (codeagent-wrapper, GitHub, Git) are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.review import app
from vibe3.services.review_runner import ReviewAgentResult

runner = CliRunner()


def _mock_review(verdict: str = "PASS"):
    m = MagicMock()
    m.verdict = verdict
    m.comments = []
    return m


def _mock_agent_result(stdout: str = "## Review\nLooks good."):
    return ReviewAgentResult(exit_code=0, stdout=stdout, stderr="")


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
            "vibe3.commands.review.run_review_agent",
            return_value=_mock_agent_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
        patch(
            "vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"
        ),
        patch("vibe3.commands.review.GitClient") as mock_git_client_class,
    ):
        # Mock GitClient to pass branch validation
        mock_git_client = MagicMock()
        mock_git_client._run.return_value = "abc123"  # Mock successful rev-parse
        mock_git_client_class.return_value = mock_git_client

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
            "vibe3.commands.review.run_review_agent",
            return_value=_mock_agent_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
        patch(
            "vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"
        ),
        patch("vibe3.commands.review.GitClient") as mock_git_client_class,
    ):
        # Mock GitClient to pass branch validation
        mock_git_client = MagicMock()
        mock_git_client._run.return_value = "abc123"  # Mock successful rev-parse
        mock_git_client_class.return_value = mock_git_client

        result = runner.invoke(app, ["base", "origin/develop"])
    assert result.exit_code == 0


def test_review_base_does_not_have_publish_option():
    """review base should NOT have --publish option."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    # --publish should NOT appear in help
    assert "--publish" not in result.output


def test_review_base_rejects_unknown_agent_param():
    """review base should reject --agent (not a valid option).

    This test ensures the hook-CLI contract is enforced: pre-push.sh
    should not use --agent parameter.
    """
    result = runner.invoke(app, ["base", "--agent", "code-reviewer"])
    # Typer should reject unknown option
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "error" in result.output.lower()
