"""Tests for flow bind command role defaults."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.FlowService")
def test_flow_update_idempotent(
    flow_service_cls,
    _render_flow_created,
) -> None:
    """flow update should ensure flow exists."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"

    flow = FlowState(
        branch="task/set-default-flow",
        flow_slug="set-default-flow",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service.get_flow_status.return_value = flow
    flow_service.ensure_flow_for_branch.return_value = flow
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["update", "--name", "set-default-flow"])

    assert result.exit_code == 0
    flow_service.ensure_flow_for_branch.assert_called_once_with(
        branch="task/set-default-flow", slug="set-default-flow"
    )


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.FlowService")
def test_flow_bind_defaults_to_task_role(flow_service_cls, task_service_cls) -> None:
    """flow bind without --role should bind as task with system ownership."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service

    result = runner.invoke(app, ["bind", "248"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/set-default-flow", 248, "task", actor=None
    )


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.FlowService")
def test_flow_bind_accepts_dependency_role(flow_service_cls, task_service_cls) -> None:
    """flow bind should allow binding dependency and related roles."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service

    result = runner.invoke(app, ["bind", "248", "--role", "dependency"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/set-default-flow", 248, "dependency", actor=None
    )


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.FlowService")
def test_flow_bind_supports_multiple_dependency_issues(
    flow_service_cls, task_service_cls
) -> None:
    """flow bind 248 249 --role dependency should bind all issues."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service
    task_service.link_issue.side_effect = [
        MagicMock(
            issue_number=248, issue_role="dependency", branch="task/set-default-flow"
        ),
        MagicMock(
            issue_number=249, issue_role="dependency", branch="task/set-default-flow"
        ),
    ]

    result = runner.invoke(app, ["bind", "248", "249", "--role", "dependency"])

    assert result.exit_code == 0
    assert task_service.link_issue.call_args_list[0].args == (
        "task/set-default-flow",
        248,
        "dependency",
    )
    assert task_service.link_issue.call_args_list[1].args == (
        "task/set-default-flow",
        249,
        "dependency",
    )
