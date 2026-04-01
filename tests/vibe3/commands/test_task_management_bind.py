"""Tests for flow bind command role semantics."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app

runner = CliRunner(env={"NO_COLOR": "1"})


def test_flow_bind_supports_related_role() -> None:
    """Test flow bind successfully binds a task to the current flow."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "219"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 219, "task", actor=None
    )


def test_flow_bind_with_task_role() -> None:
    """flow bind 220 --role task should bind as task."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "220", "--role", "task"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 220, "task", actor=None
    )


def test_flow_bind_with_related_role() -> None:
    """flow bind 219 --role related should bind as related."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "219", "--role", "related"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 219, "related", actor=None
    )


def test_flow_bind_with_dependency_role() -> None:
    """flow bind 218 --role dependency should bind as dependency."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "218", "--role", "dependency"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 218, "dependency", actor=None
    )


def test_flow_bind_with_explicit_branch_option() -> None:
    """flow bind --branch task/other 219 should bind to the specified branch."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        flow_service.get_flow_status.return_value = MagicMock()
        flow_service._is_main_branch.return_value = False
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "--branch", "task/other", "219"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/other", 219, "task", actor=None
    )


def test_flow_bind_with_explicit_protected_branch_fails() -> None:
    """flow bind --branch main should fail before linking issues."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service._is_main_branch.return_value = True
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "--branch", "main", "219"])

    assert result.exit_code != 0
    task_service.link_issue.assert_not_called()


def test_flow_bind_with_explicit_missing_flow_fails() -> None:
    """flow bind --branch task/missing should fail when the flow does not exist."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service._is_main_branch.return_value = False
        flow_service.get_flow_status.return_value = None
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app, ["bind", "--branch", "task/missing", "219"]
            )

    assert result.exit_code != 0
    task_service.link_issue.assert_not_called()
