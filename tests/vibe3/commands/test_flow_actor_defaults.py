"""Tests for flow bind command role defaults."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow_manage.render_flow_created")
@patch("vibe3.commands.flow_manage.FlowService")
@patch("vibe3.utils.branch_arg.GitClient")
def test_flow_update_idempotent(
    git_client_cls,
    flow_service_cls,
    _render_flow_created,
) -> None:
    """flow update should ensure flow exists."""
    git_client = MagicMock()
    git_client.get_current_branch.return_value = "task/set-default-flow"
    git_client_cls.return_value = git_client

    flow_service = MagicMock()
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


@patch("vibe3.commands.flow_manage.TaskService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_flow_bind_defaults_to_task_role(flow_service_cls, task_service_cls) -> None:
    """flow bind without --role should bind as task with no explicit actor."""
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


@patch("vibe3.commands.flow_manage.TaskService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_flow_bind_accepts_dependency_role(flow_service_cls, task_service_cls) -> None:
    """flow bind should allow binding dependency and related roles."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service

    result = runner.invoke(app, ["bind", "248", "--role", "dependency"])

    assert result.exit_code == 0
    flow_service.block_flow.assert_called_once_with(
        "task/set-default-flow", blocked_by_issue=248, actor=None
    )


@patch("vibe3.commands.flow_manage.TaskService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_flow_bind_supports_multiple_dependency_issues(
    flow_service_cls, task_service_cls
) -> None:
    """flow bind 248 249 --role dependency should bind all issues."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/set-default-flow"
    flow_service_cls.return_value = flow_service

    task_service = MagicMock()
    task_service_cls.return_value = task_service

    result = runner.invoke(app, ["bind", "248", "249", "--role", "dependency"])

    assert result.exit_code == 0
    assert flow_service.block_flow.call_count == 2
    assert flow_service.block_flow.call_args_list[0].kwargs["blocked_by_issue"] == 248
    assert flow_service.block_flow.call_args_list[1].kwargs["blocked_by_issue"] == 249


def test_flow_update_remains_atomic_command_surface() -> None:
    """Guard against replacing flow bootstrap with a monolithic command."""
    from vibe3.commands.flow_manage import update

    assert callable(update)


def test_flow_bind_remains_atomic_command_surface() -> None:
    """Guard against replacing flow bootstrap with a monolithic command."""
    from vibe3.commands.flow_manage import bind

    assert callable(bind)


@patch("vibe3.commands.flow_manage.FlowService")
@patch("vibe3.environment.session_registry.SessionRegistryService")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend")
def test_flow_update_blocks_when_branch_has_live_runtime_session(
    mock_backend,
    mock_registry_cls,
    mock_flow_service,
) -> None:
    """flow update should block when branch has live runtime sessions."""

    flow_service = mock_flow_service.return_value
    flow_service.get_flow_status.return_value = MagicMock(branch="task/issue-123")
    flow_service.ensure_flow_for_branch.return_value = MagicMock(
        branch="task/issue-123"
    )

    registry = mock_registry_cls.return_value
    registry.get_truly_live_sessions_for_branch.return_value = [{"id": 1}]

    with patch(
        "vibe3.utils.branch_arg.resolve_branch_arg", return_value="task/issue-123"
    ):
        result = runner.invoke(app, ["update"])

    assert result.exit_code == 1
