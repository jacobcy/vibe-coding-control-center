"""Tests for flow done command guards."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


def test_flow_done_requires_yes_when_no_task_issue() -> None:
    """Taskless flow should require --yes before closing."""
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
    flow_service.close_flow.assert_not_called()


def test_flow_done_allows_force_without_task_issue() -> None:
    """--yes should bypass the missing-task guard."""
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
        result = runner.invoke(app, ["flow", "done", "--yes"])

    assert result.exit_code == 0
    flow_service.close_flow.assert_called_once_with("task/demo", check_pr=False)
