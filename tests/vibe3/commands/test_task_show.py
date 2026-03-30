"""Tests for task show command behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.task import app
from vibe3.models.task_bridge import FieldSource, HydratedTaskView, HydrateError
from vibe3.services.task_usecase import TaskShowResult

runner = CliRunner()


def test_task_show_remote_binding_invalid_exits() -> None:
    """Broken remote binding should surface as an error, not offline output."""
    with patch("vibe3.commands.task.TaskService") as service_cls:
        service = service_cls.return_value
        service.hydrate.return_value = HydrateError(
            type="binding_invalid",
            message="GitHub Project item 'PVTI_123' no longer exists",
        )

        result = runner.invoke(app, ["show", "task/test-branch"])

    assert result.exit_code == 1
    assert "no longer exists" in result.output


def test_task_show_defaults_to_current_branch_when_missing_argument() -> None:
    """task show without BRANCH should fallback to current git branch."""
    with (
        patch("vibe3.commands.task.FlowService") as flow_service_cls,
        patch("vibe3.commands.task.TaskService") as service_cls,
    ):
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/set-default-flow"
        flow_service_cls.return_value = flow_service

        service = service_cls.return_value
        service.hydrate.return_value = HydrateError(
            type="binding_invalid",
            message="GitHub Project item 'PVTI_123' no longer exists",
        )

        result = runner.invoke(app, ["show"])

    assert result.exit_code == 1
    service.hydrate.assert_called_once_with("task/set-default-flow")


def test_task_show_prompts_flow_bind_when_task_is_unbound() -> None:
    """Unbound tasks should point users to flow bind."""
    with (
        patch("vibe3.commands.task.FlowService") as flow_service_cls,
        patch("vibe3.commands.task.TaskService") as service_cls,
    ):
        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/set-default-flow"
        flow_service_cls.return_value = flow_service

        service = service_cls.return_value
        service.hydrate.return_value = HydrateError(
            type="no_remote_identity",
            message="Branch 'task/set-default-flow' 未绑定 GitHub Project item",
        )
        service.get_task.return_value = type(
            "Task",
            (),
            {
                "branch": "task/set-default-flow",
                "task_issue_number": 248,
                "flow_status": "active",
            },
        )()

        result = runner.invoke(app, ["show"])

    assert result.exit_code == 0
    assert "未绑定 GitHub Project item" in result.output
    assert "task bridge" not in result.output


def test_task_show_renders_remote_body_when_available() -> None:
    """task show should render remote body when hydrate includes it."""
    view = HydratedTaskView(
        branch="task/demo",
        project_item_id=FieldSource(value="PVTI_123", source="local"),
        title=FieldSource(value="Demo title", source="remote"),
        body=FieldSource(value="Demo body", source="remote"),
    )
    result_payload = TaskShowResult(
        branch="task/demo",
        view=view,
        related_issue_numbers=[],
        dependency_issue_numbers=[],
    )
    usecase = MagicMock()
    usecase.resolve_branch.return_value = "task/demo"
    usecase.show_task.return_value = result_payload

    mock_milestone_svc = MagicMock()
    mock_milestone_svc.get_milestone_context.return_value = None

    with (
        patch("vibe3.commands.task._build_task_usecase", return_value=usecase),
        patch(
            "vibe3.commands.task._build_milestone_service",
            return_value=mock_milestone_svc,
        ),
    ):
        result = runner.invoke(app, ["show", "task/demo"])

    assert result.exit_code == 0
    assert "Demo title" in result.output
    assert "Demo body" in result.output
