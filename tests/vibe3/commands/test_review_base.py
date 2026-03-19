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


def _mock_inspect_data():
    return {
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def _mock_agent_result(stdout: str = "## Review\nLooks good."):
    return ReviewAgentResult(exit_code=0, stdout=stdout, stderr="")


def _patch_review_deps(verdict: str = "PASS"):
    """Return patch context list, mocking all external dependencies."""
    return [
        patch(
            "vibe3.commands.review.run_inspect_json", return_value=_mock_inspect_data()
        ),
        patch("vibe3.commands.review.GitClient"),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.run_review_agent",
            return_value=_mock_agent_result(),
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review(verdict),
        ),
        patch("vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"),
    ]


def test_review_base_defaults_to_origin_main():
    """Test that review base defaults to origin/main when no branch specified."""
    with (
        patch(
            "vibe3.commands.review.run_inspect_json", return_value=_mock_inspect_data()
        ) as mock_inspect,
        patch("vibe3.commands.review.GitClient") as mock_git,
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
    ):
        result = runner.invoke(app, ["base"])
        assert result.exit_code == 0
        # Verify inspect was called with origin/main
        mock_inspect.assert_called_once_with(["base", "origin/main"])
        # Verify GitClient.get_diff was called with origin/main
        mock_git.return_value.get_diff.assert_called_once()
        call_args = mock_git.return_value.get_diff.call_args[0][0]
        assert call_args.base == "origin/main"
        assert call_args.branch == "feature/test"


def test_review_base_pass():
    patches = _patch_review_deps()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = runner.invoke(app, ["base", "origin/develop"])
    assert result.exit_code == 0


def test_review_base_with_agent_and_model():
    """Test that --agent and --model options are passed through."""
    with (
        patch(
            "vibe3.commands.review.run_inspect_json", return_value=_mock_inspect_data()
        ),
        patch("vibe3.commands.review.GitClient"),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.run_review_agent",
            return_value=_mock_agent_result(),
        ) as mock_run,
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review("PASS"),
        ),
        patch("vibe3.utils.git_helpers.get_current_branch", return_value="feature/test"),
    ):
        result = runner.invoke(
            app, ["base", "origin/develop", "--agent", "codex", "--model", "gpt-5.4"]
        )
    assert result.exit_code == 0
    # Verify options were passed to run_review_agent
    call_args = mock_run.call_args
    options = call_args[0][1]
    assert options.agent.value == "codex"
    assert options.model == "gpt-5.4"


def test_review_base_does_not_have_publish_option():
    """review base should NOT have --publish option."""
    result = runner.invoke(app, ["base", "--help"])
    assert result.exit_code == 0
    # --publish should NOT appear in help
    assert "--publish" not in result.output
