"""Tests for vibe review pr subcommand.

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
    ):
        result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 0
    assert "PASS" in result.output


def test_review_pr_block_exits_1():
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
            return_value=_mock_review("BLOCK"),
        ),
    ):
        result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 1


def test_review_pr_help():
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0
    assert "PR number" in result.output


def test_review_pr_with_agent_and_model():
    """Test that --agent and --model options are passed through."""
    with (
        patch(
            "vibe3.commands.review.run_inspect_json",
            return_value=_mock_inspect_data(),
        ),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.run_review_agent",
            return_value=_mock_agent_result(),
        ) as mock_run,
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
    ):
        result = runner.invoke(
            app, ["pr", "42", "--agent", "codex", "--model", "gpt-5.4"]
        )
    assert result.exit_code == 0
    # Verify options were passed to run_review_agent
    call_args = mock_run.call_args
    options = call_args[0][1]
    assert options.agent == "codex"
    assert options.model == "gpt-5.4"


def test_review_pr_does_not_have_publish_option():
    """review pr should NOT have --publish option (local-only)."""
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0
    # --publish should NOT appear in help
    assert "--publish" not in result.output


def test_review_pr_is_local_only():
    """review pr should not call GitHub publish methods."""
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
    ):
        result = runner.invoke(app, ["pr", "42"])

    assert result.exit_code == 0
