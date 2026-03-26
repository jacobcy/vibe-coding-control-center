"""Tests for flow command default actor behavior."""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.flow import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.HandoffService")
@patch("vibe3.commands.flow.render_flow_created")
@patch("vibe3.commands.flow.SQLiteClient")
@patch("vibe3.commands.flow.FlowService")
@patch("vibe3.commands.flow.GitClient")
def test_flow_new_task_bound_uses_system_actor_by_default(
    git_cls,
    flow_service_cls,
    sqlite_cls,
    _render_flow_created,
    _handoff_service_cls,
) -> None:
    """flow new without --actor should write task_bound actor as system."""
    git = git_cls.return_value
    git.get_current_branch.return_value = "task/set-default-flow"

    flow = FlowState(
        branch="task/set-default-flow",
        flow_slug="set-default-flow",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service_cls.return_value.get_flow_status.return_value = None
    flow_service_cls.return_value.create_flow.return_value = flow

    result = runner.invoke(app, ["new", "set-default-flow", "--task", "248"])

    assert result.exit_code == 0
    sqlite = sqlite_cls.return_value
    sqlite.add_event.assert_called_once_with(
        "task/set-default-flow",
        "task_bound",
        "system",
        detail="Task bound: 248",
    )


@patch("vibe3.commands.flow.SQLiteClient")
@patch("vibe3.commands.flow.GitClient")
def test_flow_bind_uses_system_actor_by_default(git_cls, sqlite_cls) -> None:
    """flow bind without --actor should write task_bound actor as system."""
    git = git_cls.return_value
    git.get_current_branch.return_value = "task/set-default-flow"

    result = runner.invoke(app, ["bind", "248"])

    assert result.exit_code == 0
    sqlite = sqlite_cls.return_value
    sqlite.add_event.assert_called_once_with(
        "task/set-default-flow",
        "task_bound",
        "system",
        detail="Task bound: 248",
    )
