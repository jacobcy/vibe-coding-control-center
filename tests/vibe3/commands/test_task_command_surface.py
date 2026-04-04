"""Tests for task command surface."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner(env={"NO_COLOR": "1"})


@patch("vibe3.commands.task.GitHubClient")
@patch("vibe3.commands.task.render_task_show_with_milestone")
@patch("vibe3.commands.task.TaskUsecase")
@patch("vibe3.commands.task.MilestoneService")
def test_task_show_comments_outputs_latest_human_instruction(
    mock_milestone_service_cls,
    mock_task_usecase_cls,
    _render_task_show,
    mock_github_client_cls,
) -> None:
    """task show --comments should print latest comment and latest human comment."""
    usecase = MagicMock()
    usecase.resolve_branch.return_value = "task/issue-372"
    usecase.show_task.return_value = MagicMock(
        local_task=FlowStatusResponse(
            branch="task/issue-372",
            flow_slug="issue-372",
            flow_status="active",
            task_issue_number=372,
        )
    )
    mock_task_usecase_cls.return_value = usecase

    milestone_svc = MagicMock()
    milestone_svc.get_milestone_context.return_value = None
    mock_milestone_service_cls.return_value = milestone_svc

    github = MagicMock()
    github.view_issue.return_value = {
        "number": 372,
        "title": "Task 372",
        "state": "OPEN",
        "labels": [{"name": "state/ready"}],
        "comments": [
            {"author": {"login": "linear"}, "body": "system sync"},
            {"author": {"login": "jacobcy"}, "body": "continue debugging"},
        ],
    }
    mock_github_client_cls.return_value = github

    result = runner.invoke(app, ["task", "show", "--comments"])

    assert result.exit_code == 0
    assert "Latest Comment:" in result.stdout
    assert "Latest Human Instruction:" in result.stdout
    assert "continue debugging" in result.stdout
    assert "jacobcy" in result.stdout


@patch("vibe3.commands.status.status")
def test_task_status_delegates_to_status_command(mock_status) -> None:
    """task status should reuse the unified status dashboard."""
    result = runner.invoke(app, ["task", "status", "--all", "--json"])

    assert result.exit_code == 0
    mock_status.assert_called_once_with(all_flows=True, json_output=True, trace=False)


@patch("vibe3.commands.status.status")
def test_top_level_status_is_hidden_compat_alias(mock_status) -> None:
    """top-level status should still delegate for compatibility."""
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    mock_status.assert_called_once_with(all_flows=False, json_output=False, trace=False)
