"""Tests for flow blocked command --pr option."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.pr import PRResponse, PRState

runner = CliRunner()


def test_flow_blocked_supports_pr_option() -> None:
    """--pr should resolve head branch and block that flow."""
    flow_service = MagicMock()
    pr_service = MagicMock()
    pr_service.get_pr.return_value = PRResponse(
        number=789,
        title="Test PR",
        body="",
        state=PRState.OPEN,
        head_branch="task/from-pr",
        base_branch="main",
        url="https://example.com/pr/789",
        merged_at=None,
    )

    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service),
    ):
        result = runner.invoke(
            app, ["flow", "blocked", "--pr", "789", "--reason", "waiting"]
        )

    assert result.exit_code == 0
    pr_service.get_pr.assert_called_once_with(pr_number=789)
    flow_service.block_flow.assert_called_once_with(
        "task/from-pr", reason="waiting", blocked_by_issue=None
    )


def test_flow_blocked_rejects_branch_and_pr_together() -> None:
    """--branch and --pr are mutually exclusive for blocked."""
    result = runner.invoke(
        app,
        ["flow", "blocked", "--branch", "task/demo", "--pr", "789"],
    )

    assert result.exit_code == 1
    assert "不能同时指定 --branch 与 --pr" in result.output


def test_flow_blocked_reports_missing_pr() -> None:
    """--pr should fail clearly when PR number cannot be resolved."""
    pr_service = MagicMock()
    pr_service.get_pr.return_value = None

    with patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service):
        result = runner.invoke(app, ["flow", "blocked", "--pr", "999"])

    assert result.exit_code == 1
    assert "未找到 PR #999" in result.output
