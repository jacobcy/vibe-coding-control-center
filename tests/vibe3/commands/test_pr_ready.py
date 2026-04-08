"""Tests for PR ready command."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.pr import app
from vibe3.services.pr_ready_usecase import PrReadyAbortedError

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def test_pr_ready_without_arg_resolves_pr_from_flow_state(mock_pr_response):
    """pr ready (missing PR number) should resolve from current flow PR."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
        patch(
            "vibe3.commands.pr_lifecycle._build_pr_ready_usecase"
        ) as mock_build_usecase,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.store.get_flow_state.return_value = {"pr_number": 123}
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/demo"
        mock_flow_service.return_value = mock_flow_instance

        mock_usecase = MagicMock()
        mock_usecase.mark_ready.return_value = mock_pr_response
        mock_build_usecase.return_value = mock_usecase

        result = runner.invoke(app, ["ready", "--yes"])

        assert result.exit_code == 0
        mock_usecase.mark_ready.assert_called_once_with(
            pr_number=123, yes=True, requested_reviewers=None
        )


def test_pr_ready_without_arg_and_no_current_pr_shows_error():
    """pr ready (missing PR number) should fail with clear hint when no PR found."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch("vibe3.commands.pr_lifecycle.FlowService") as mock_flow_service,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_instance.store.get_flow_state.return_value = {}
        mock_pr_instance.get_pr.return_value = None
        mock_pr_service.return_value = mock_pr_instance

        mock_flow_instance = MagicMock()
        mock_flow_instance.get_current_branch.return_value = "task/no-pr"
        mock_flow_service.return_value = mock_flow_instance

        result = runner.invoke(app, ["ready", "--yes"])

        assert result.exit_code == 1
        assert "No PR found for current branch 'task/no-pr'" in result.output
        assert "vibe3 pr ready <PR_NUMBER>" in result.output


def test_pr_ready_help():
    """pr ready --help shows usage."""
    result = runner.invoke(app, ["ready", "--help"])
    output = _strip_ansi(result.output)
    assert result.exit_code == 0
    assert "PR number" in output
    assert "--yes" in output
    assert "reviewer briefing" in output


def test_pr_ready_user_abort_exits_zero():
    """pr ready confirmation abort should exit 0 without string-matching errors."""
    aborted_usecase = MagicMock()
    aborted_usecase.mark_ready.side_effect = PrReadyAbortedError("aborted by user")

    with patch(
        "vibe3.commands.pr_lifecycle._build_pr_ready_usecase",
        return_value=aborted_usecase,
    ):
        result = runner.invoke(app, ["ready", "123"])

    assert result.exit_code == 0


def test_pr_ready_json_output(mock_pr_response):
    """pr ready --json outputs JSON format."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.commands.pr_lifecycle._build_pr_ready_usecase"
        ) as mock_build_usecase,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_service.return_value = mock_pr_instance

        mock_usecase = MagicMock()
        mock_usecase.mark_ready.return_value = mock_pr_response
        mock_build_usecase.return_value = mock_usecase

        result = runner.invoke(app, ["ready", "123", "--yes", "--json"])

        assert result.exit_code == 0
        assert '"number": 123' in result.output
        assert '"title": "Test PR"' in result.output


def test_pr_ready_yaml_output(mock_pr_response):
    """pr ready --yaml outputs YAML format."""
    with (
        patch("vibe3.commands.pr_lifecycle.PRService") as mock_pr_service,
        patch(
            "vibe3.commands.pr_lifecycle._build_pr_ready_usecase"
        ) as mock_build_usecase,
    ):
        mock_pr_instance = MagicMock()
        mock_pr_service.return_value = mock_pr_instance

        mock_usecase = MagicMock()
        mock_usecase.mark_ready.return_value = mock_pr_response
        mock_build_usecase.return_value = mock_usecase

        result = runner.invoke(app, ["ready", "123", "--yes", "--yaml"])

        assert result.exit_code == 0
        assert "number: 123" in result.output
        assert "title: Test PR" in result.output
