"""Tests for flow done command guards."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState

runner = CliRunner()


def test_flow_done_allows_missing_task_issue_and_delegates_pr_guard() -> None:
    """Taskless flow should still proceed to close_flow(PR guard happens in service)."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
        issues=[],
    )

    with patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service):
        result = runner.invoke(app, ["flow", "done"])

    assert result.exit_code == 0
    flow_service.close_flow.assert_called_once_with("task/demo", check_pr=True)


def test_flow_done_passes_pr_check_when_task_issue_exists() -> None:
    """Task-bound flow should close with PR merge check enabled."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=123,
        issues=[],
    )

    with patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service):
        result = runner.invoke(app, ["flow", "done"])

    assert result.exit_code == 0
    flow_service.close_flow.assert_called_once_with("task/demo", check_pr=True)


def test_flow_done_supports_pr_option() -> None:
    """--pr should resolve head branch and close that flow."""
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/from-pr",
        flow_slug="from-pr",
        flow_status="active",
        task_issue_number=None,
        issues=[],
    )
    pr_service = MagicMock()
    pr_service.get_pr.return_value = PRResponse(
        number=456,
        title="Test PR",
        body="",
        state=PRState.MERGED,
        head_branch="task/from-pr",
        base_branch="main",
        url="https://example.com/pr/456",
        merged_at=None,
    )

    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service),
    ):
        result = runner.invoke(app, ["flow", "done", "--pr", "456"])

    assert result.exit_code == 0
    pr_service.get_pr.assert_called_once_with(pr_number=456)
    flow_service.get_flow_status.assert_called_once_with("task/from-pr")
    flow_service.close_flow.assert_called_once_with("task/from-pr", check_pr=True)


def test_flow_done_rejects_branch_and_pr_together() -> None:
    """--branch and --pr are mutually exclusive for done."""
    result = runner.invoke(
        app,
        ["flow", "done", "--branch", "task/demo", "--pr", "456"],
    )

    assert result.exit_code == 1
    assert "不能同时指定 --branch 与 --pr" in result.output


def test_flow_done_reports_missing_pr() -> None:
    """--pr should fail clearly when PR number cannot be resolved."""
    pr_service = MagicMock()
    pr_service.get_pr.return_value = None

    with patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service):
        result = runner.invoke(app, ["flow", "done", "--pr", "999"])

    assert result.exit_code == 1
    assert "未找到 PR #999" in result.output
