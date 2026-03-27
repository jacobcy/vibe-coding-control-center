"""Tests for flow done command guards."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


def test_flow_done_requires_task_issue_when_no_task_issue() -> None:
    """Taskless flow should fail and suggest bind/abort."""
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

    assert result.exit_code == 1
    assert "未绑定 task issue" in result.output
    assert "vibe3 flow bind <issue> --role task" in result.output
    assert "vibe3 flow aborted" in result.output
    flow_service.close_flow.assert_not_called()


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
