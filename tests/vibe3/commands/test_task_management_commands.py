"""Tests for flow/task command parameter semantics."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app
from vibe3.commands.task import app as task_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_flow_new_help_uses_optional_name_and_issue_flag() -> None:
    result = runner.invoke(flow_app, ["new", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root new [OPTIONS] NAME" in stdout
    assert "--task" in stdout or "--spec" in stdout


def test_flow_bind_help_uses_issue_and_role() -> None:
    result = runner.invoke(flow_app, ["bind", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root bind [OPTIONS] ISSUE" in stdout
    assert "Issue reference to bind as task/related/dependency" in stdout
    assert "--role" in stdout
    assert "Issue role" in stdout
    assert "actor" not in stdout


def test_flow_show_help_uses_branch_option() -> None:
    result = runner.invoke(flow_app, ["show", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root show [OPTIONS]" in stdout
    assert "--branch" in stdout
    assert "Branch name" in stdout


def test_flow_switch_help_uses_branch_option() -> None:
    result = runner.invoke(flow_app, ["switch", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root switch [OPTIONS]" in stdout
    assert "--branch" in stdout
    assert "Branch name or flow slug" in stdout


def test_task_link_command_removed() -> None:
    result = runner.invoke(task_app, ["link", "--help"])

    assert result.exit_code != 0
    assert "No such command" in (result.stdout + result.stderr)


def test_task_list_help_uses_issue_option() -> None:
    result = runner.invoke(task_app, ["list", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--issue" in stdout
    assert "--repo-issue" not in stdout


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
    task_service.link_issue.assert_called_once_with("task/demo", 219, "task")


def test_task_status_command_removed() -> None:
    result = runner.invoke(task_app, ["status", "Done"])

    assert result.exit_code != 0
    assert "No such command" in (result.stdout + result.stderr)


# ==============================================================================
# Task 1 Tests: Issue-based task semantics for flow CLI
# ==============================================================================


def test_flow_create_task_option_help_shows_issue_reference() -> None:
    """--task option should describe issue reference, not arbitrary task ID."""
    result = runner.invoke(flow_app, ["create", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    # --task help should mention "issue" in description
    assert "--task" in stdout
    # Should describe it as issue reference, not arbitrary task ID
    assert "issue" in stdout.lower() or "Issue" in stdout


def test_flow_create_spec_option_help() -> None:
    """--spec option should be the primary spec reference option."""
    result = runner.invoke(flow_app, ["create", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--spec" in stdout


def test_flow_blocked_help_shows_task_option() -> None:
    """flow blocked should show --task option for dependency issue."""
    result = runner.invoke(flow_app, ["blocked", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    # Should have --task option visible
    assert "--task" in stdout
    # Should describe it as issue reference for blocking dependency
    assert "issue" in stdout.lower() or "Issue" in stdout


def test_flow_blocked_help_still_shows_by_for_backward_compat() -> None:
    """flow blocked --by should remain for backward compatibility."""
    result = runner.invoke(flow_app, ["blocked", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    # --by should still be available for backward compat
    assert "--by" in stdout


def test_flow_bind_positional_arg_is_issue() -> None:
    """flow bind positional argument should be ISSUE (not TASK_ID)."""
    result = runner.invoke(flow_app, ["bind", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    # Argument should be named ISSUE
    assert "ISSUE" in stdout or "issue" in stdout.lower()


def test_flow_bind_role_option_has_all_roles() -> None:
    """flow bind --role should support task, related, dependency."""
    result = runner.invoke(flow_app, ["bind", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--role" in stdout
    assert "task" in stdout
    assert "related" in stdout
    assert "dependency" in stdout


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
    task_service.link_issue.assert_called_once_with("task/demo", 220, "task")


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
    task_service.link_issue.assert_called_once_with("task/demo", 219, "related")


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
    task_service.link_issue.assert_called_once_with("task/demo", 218, "dependency")


def test_flow_bind_with_multiple_related_roles() -> None:
    """flow bind 219 220 --role related should bind both issues."""
    with patch("vibe3.commands.flow.TaskService", create=True) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service
        task_service.link_issue.side_effect = [
            MagicMock(issue_number=219, issue_role="related", branch="task/demo"),
            MagicMock(issue_number=220, issue_role="related", branch="task/demo"),
        ]

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app, ["bind", "219", "220", "--role", "related"]
            )

    assert result.exit_code == 0
    assert task_service.link_issue.call_args_list[0].args == (
        "task/demo",
        219,
        "related",
    )
    assert task_service.link_issue.call_args_list[1].args == (
        "task/demo",
        220,
        "related",
    )
