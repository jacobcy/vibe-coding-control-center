"""Tests for task-binding guidance in flow/pr commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.render_flow_timeline")
@patch("vibe3.commands.flow.ensure_flow_for_current_branch")
def test_flow_show_warns_when_task_issue_missing(mock_ensure, _render_timeline) -> None:
    """flow show should suggest binding a task when none is present."""
    flow_service = MagicMock()
    flow_service.get_flow_timeline.return_value = {
        "state": FlowState(
            branch="task/demo",
            flow_slug="demo",
            flow_status="active",
            task_issue_number=None,
        ),
        "events": [],
    }
    mock_ensure.return_value = (flow_service, "task/demo")

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    assert "还没有 task" in result.stdout
    assert "vibe3 flow bind <issue> --role task" in result.stdout


@patch("vibe3.commands.pr_create.render_pr_created")
@patch("vibe3.commands.pr_create.PRService")
@patch("vibe3.commands.pr_create.FlowService")
def test_pr_create_warns_when_task_issue_missing(
    mock_flow_service_cls, mock_pr_service_cls, _render_pr_created
) -> None:
    """pr create should warn but continue when current flow has no task."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    mock_flow_service_cls.return_value = flow_service

    mock_pr_service = MagicMock()
    mock_pr_service.create_draft_pr.return_value = MagicMock(model_dump=lambda: {})
    mock_pr_service_cls.return_value = mock_pr_service

    result = runner.invoke(app, ["pr", "create", "-t", "Test PR"])

    assert result.exit_code == 0
    assert "还没有 task" in result.stdout
    assert "建议先执行 vibe3 flow bind <issue> --role task" in result.stdout


@patch("vibe3.commands.pr_query.PRService")
@patch("vibe3.commands.pr_query.FlowService")
def test_pr_show_missing_pr_includes_bind_hint(
    mock_flow_service_cls, mock_pr_service_cls
) -> None:
    """pr show should include bind hint when current flow has no task."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    mock_flow_service_cls.return_value = flow_service

    pr_service = MagicMock()
    pr_service.store.get_flow_state.return_value = None
    pr_service.get_pr.return_value = None
    mock_pr_service_cls.return_value = pr_service

    result = runner.invoke(app, ["pr", "show"])

    assert result.exit_code == 1
    assert "No PR found for current branch 'task/demo'" in result.output
    assert "vibe3 flow bind <issue> --role task" in result.output
