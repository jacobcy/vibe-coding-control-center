"""Tests for flow/task command parameter semantics."""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app
from vibe3.commands.task import app as task_app

runner = CliRunner()


def test_flow_new_help_uses_optional_name_and_issue_flag() -> None:
    result = runner.invoke(flow_app, ["new", "--help"])

    assert result.exit_code == 0
    assert "Usage: root new [OPTIONS] [NAME]" in result.stdout
    assert "--issue" in result.stdout
    assert "--task-issue" not in result.stdout


def test_flow_bind_help_uses_issue_and_role() -> None:
    result = runner.invoke(flow_app, ["bind", "--help"])

    assert result.exit_code == 0
    assert "Usage: root bind [OPTIONS] ISSUE" in result.stdout
    assert "--role" in result.stdout
    assert "task|related|dependency" in result.stdout
    assert "TASK_ID" not in result.stdout


def test_flow_show_help_uses_branch_name() -> None:
    result = runner.invoke(flow_app, ["show", "--help"])

    assert result.exit_code == 0
    assert "Usage: root show [OPTIONS] [BRANCH]" in result.stdout
    assert "Branch name" in result.stdout
    assert "FLOW_NAME" not in result.stdout


def test_task_link_help_uses_issue_and_new_roles() -> None:
    result = runner.invoke(task_app, ["link", "--help"])

    assert result.exit_code == 0
    assert "Usage: root link [OPTIONS] ISSUE" in result.stdout
    assert "related|dependency" in result.stdout
    assert "task|repo" not in result.stdout
    assert "ISSUE_URL" not in result.stdout


def test_task_list_help_uses_issue_option() -> None:
    result = runner.invoke(task_app, ["list", "--help"])

    assert result.exit_code == 0
    assert "--issue" in result.stdout
    assert "--repo-issue" not in result.stdout


def test_flow_bind_supports_related_role() -> None:
    issue_link = Mock()
    issue_link.model_dump.return_value = {"issue_role": "related"}

    with (
        patch("vibe3.commands.flow.GitClient") as git_cls,
        patch("vibe3.commands.flow.TaskService") as task_service_cls,
        patch("vibe3.commands.flow.parse_issue_ref", return_value=219),
        patch("vibe3.commands.flow.render_issue_linked"),
    ):
        git_cls.return_value.get_current_branch.return_value = "task/demo"
        task_service_cls.return_value.link_issue.return_value = issue_link

        result = runner.invoke(flow_app, ["bind", "219", "--role", "related"])

    assert result.exit_code == 0
    task_service_cls.return_value.link_issue.assert_called_once_with(
        "task/demo", 219, role="related"
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
