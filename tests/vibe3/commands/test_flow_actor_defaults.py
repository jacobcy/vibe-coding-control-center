"""Tests for flow bind command role defaults."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.flow import app
from vibe3.models.flow import CreateDecision, FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.HandoffService")
@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.FlowService")
def test_flow_add_task_bound_uses_system_actor_by_default(
    flow_service_cls,
    _render_flow_created,
    _handoff_service_cls,
    task_service_cls,
) -> None:
    """flow add without --actor should link task issue with system ownership."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"

    flow = FlowState(
        branch="task/set-default-flow",
        flow_slug="set-default-flow",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = flow
    flow_service_cls.return_value = flow_service
    task_service_cls.return_value = task_service

    result = runner.invoke(app, ["add", "set-default-flow", "--task", "248"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/set-default-flow", 248, "task", actor=None
    )


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.HandoffService")
@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.FlowService")
def test_flow_add_supports_multiple_task_refs_in_single_flag_style(
    flow_service_cls,
    _render_flow_created,
    _handoff_service_cls,
    task_service_cls,
) -> None:
    """flow add --task 281 282 should bind both task issues."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/set-default-flow",
        flow_slug="set-default-flow",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service.store = MagicMock()
    flow_service_cls.return_value = flow_service
    task_service_cls.return_value = task_service
    task_service.link_issue.side_effect = [
        MagicMock(issue_number=281, issue_role="task", branch="task/set-default-flow"),
        MagicMock(issue_number=282, issue_role="task", branch="task/set-default-flow"),
    ]

    result = runner.invoke(app, ["add", "set-default-flow", "--task", "281", "282"])

    assert result.exit_code == 0
    assert task_service.link_issue.call_args_list[0].args == (
        "task/set-default-flow",
        281,
        "task",
    )
    assert task_service.link_issue.call_args_list[1].args == (
        "task/set-default-flow",
        282,
        "task",
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


@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.HandoffService")
@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.FlowService")
def test_flow_create_supports_multiple_task_refs_in_single_flag_style(
    flow_service_cls,
    _render_flow_created,
    _handoff_service_cls,
    task_service_cls,
) -> None:
    """flow create --task 281 282 should bind both task issues."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "main"
    flow_service.resolve_flow_name.return_value = "multi-task"
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=True,
        reason="No active flow in current worktree",
        start_ref="origin/main",
        requires_new_worktree=False,
    )
    flow_service.create_flow_with_branch.return_value = FlowState(
        branch="task/multi-task",
        flow_slug="multi-task",
        flow_status="active",
    )
    flow_service.store = MagicMock()
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service
    task_service.link_issue.side_effect = [
        MagicMock(issue_number=281, issue_role="task", branch="task/multi-task"),
        MagicMock(issue_number=282, issue_role="task", branch="task/multi-task"),
    ]

    result = runner.invoke(app, ["create", "multi-task", "--task", "281", "282"])

    assert result.exit_code == 0
    assert task_service.link_issue.call_args_list[0].args == (
        "task/multi-task",
        281,
        "task",
    )
    assert task_service.link_issue.call_args_list[1].args == (
        "task/multi-task",
        282,
        "task",
    )


@pytest.mark.parametrize(
    "name",
    ["issue465", "issue-465", "issue_465", "task465", "task-465", "task_465"],
)
@patch("vibe3.commands.flow.TaskService")
@patch("vibe3.commands.flow.HandoffService")
@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.FlowService")
def test_flow_create_infers_task_from_supported_name_patterns(
    flow_service_cls,
    _render_flow_created,
    _handoff_service_cls,
    task_service_cls,
    name: str,
) -> None:
    """flow create should infer task issue from issue/task shorthand names."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "main"
    flow_service.resolve_flow_name.return_value = name
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=True,
        reason="No active flow in current worktree",
        start_ref="origin/main",
        requires_new_worktree=False,
    )
    flow_service.create_flow_with_branch.return_value = FlowState(
        branch=f"task/{name}",
        flow_slug=name,
        flow_status="active",
    )
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service
    task_service.link_issue.return_value = MagicMock(
        issue_number=465, issue_role="task", branch=f"task/{name}"
    )

    result = runner.invoke(app, ["create", name])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        f"task/{name}",
        465,
        "task",
        actor=None,
    )
