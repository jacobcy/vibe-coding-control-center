"""Tests for flow/task command parameter semantics."""

import re
from unittest.mock import Mock, patch

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
    assert "Usage: root bind [OPTIONS] TASK_ID" in stdout
    assert "TASK_ID" in stdout


def test_flow_show_help_uses_branch_name() -> None:
    result = runner.invoke(flow_app, ["show", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root show [OPTIONS] [FLOW_NAME]" in stdout
    assert "Flow to show" in stdout


def test_task_link_help_uses_issue_and_new_roles() -> None:
    result = runner.invoke(task_app, ["link", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Usage: root link [OPTIONS] ISSUE" in stdout
    assert "related|dependency" in stdout
    assert "task|repo" not in stdout
    assert "ISSUE_URL" not in stdout


def test_task_list_help_uses_issue_option() -> None:
    result = runner.invoke(task_app, ["list", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--issue" in stdout
    assert "--repo-issue" not in stdout


def test_flow_bind_supports_related_role() -> None:
    """Test flow bind successfully binds a task to the current flow."""
    with (
        patch("vibe3.commands.flow.GitClient") as git_cls,
        patch("vibe3.commands.flow.SQLiteClient") as store_cls,
    ):
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        store_cls.return_value.add_issue_link.return_value = None
        store_cls.return_value.update_flow_state.return_value = None
        store_cls.return_value.add_event.return_value = None

        result = runner.invoke(flow_app, ["bind", "219"])

    assert result.exit_code == 0
    store_cls.return_value.add_issue_link.assert_called_once_with(
        "task/demo", 219, "task"
    )


def test_task_link_defaults_to_related_role() -> None:
    issue_link = Mock()

    with (
        patch("vibe3.commands.task.GitClient") as git_cls,
        patch("vibe3.commands.task.TaskService") as task_service_cls,
        patch("vibe3.commands.task.render_issue_linked"),
    ):
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        task_service_cls.return_value.link_issue.return_value = issue_link

        result = runner.invoke(task_app, ["link", "219"])

    assert result.exit_code == 0
    task_service_cls.return_value.link_issue.assert_called_once_with(
        "task/demo", 219, "related"
    )
