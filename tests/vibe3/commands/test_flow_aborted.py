"""Tests for flow aborted command guards."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState

runner = CliRunner()


def test_flow_aborted_rejects_missing_flow() -> None:
    """Aborting a branch with no flow should fail with clear error."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "do/20260329-5f79a6"
    flow_service.get_flow_status.return_value = None

    with patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service):
        result = runner.invoke(
            app, ["flow", "aborted", "--branch", "do/20260329-5f79a6"]
        )

    assert result.exit_code == 1
    assert "没有 flow" in result.output
    flow_service.abort_flow.assert_not_called()


def test_flow_aborted_succeeds_when_flow_exists() -> None:
    """Aborting a branch with an existing flow should proceed."""
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
        result = runner.invoke(app, ["flow", "aborted", "--branch", "task/demo"])

    assert result.exit_code == 0
    flow_service.abort_flow.assert_called_once_with("task/demo")


def test_flow_aborted_supports_pr_option() -> None:
    """--pr should resolve head branch and abort that flow."""
    flow_service = MagicMock()
    pr_service = MagicMock()
    pr_service.get_pr.return_value = PRResponse(
        number=101,
        title="Test PR",
        body="",
        state=PRState.CLOSED,
        head_branch="task/from-pr",
        base_branch="main",
        url="https://example.com/pr/101",
        merged_at=None,
    )

    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service),
    ):
        result = runner.invoke(app, ["flow", "aborted", "--pr", "101"])

    assert result.exit_code == 0
    pr_service.get_pr.assert_called_once_with(pr_number=101)
    flow_service.abort_flow.assert_called_once_with("task/from-pr")


def test_flow_aborted_rejects_branch_and_pr_together() -> None:
    """--branch and --pr are mutually exclusive for aborted."""
    result = runner.invoke(
        app,
        ["flow", "aborted", "--branch", "task/demo", "--pr", "101"],
    )

    assert result.exit_code == 1
    assert "不能同时指定 --branch 与 --pr" in result.output


def test_flow_aborted_reports_missing_pr() -> None:
    """--pr should fail clearly when PR number cannot be resolved."""
    pr_service = MagicMock()
    pr_service.get_pr.return_value = None

    with patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service):
        result = runner.invoke(app, ["flow", "aborted", "--pr", "999"])

    assert result.exit_code == 1
    assert "未找到 PR #999" in result.output
