"""Tests for task command surface."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.services.status_service import OrchestraSnapshot

runner = CliRunner(env={"NO_COLOR": "1"})


@patch("vibe3.commands.task.TaskService")
@patch("vibe3.commands.task.render_task_show_with_milestone")
@patch("vibe3.commands.task.MilestoneService")
def test_task_show_comments_outputs_latest_human_instruction(
    mock_milestone_service_cls,
    _render_task_show,
    mock_task_service_cls,
) -> None:
    """task show --comments should print latest comment and latest human comment."""
    task_svc = MagicMock()
    task_svc.resolve_branch.return_value = "task/issue-372"
    task_svc.show_task.return_value = MagicMock(
        local_task=FlowStatusResponse(
            branch="task/issue-372",
            flow_slug="issue-372",
            flow_status="active",
            task_issue_number=372,
        )
    )
    task_svc.fetch_issue_with_comments.return_value = {
        "number": 372,
        "title": "Task 372",
        "state": "OPEN",
        "labels": [{"name": "state/ready"}],
        "comments": [
            {"author": {"login": "linear"}, "body": "system sync"},
            {"author": {"login": "jacobcy"}, "body": "continue debugging"},
        ],
    }
    mock_task_service_cls.return_value = task_svc

    milestone_svc = MagicMock()
    milestone_svc.get_milestone_context.return_value = None
    mock_milestone_service_cls.return_value = milestone_svc

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
    mock_status.assert_called_once_with(
        all_flows=True, check=False, json_output=True, trace=False
    )


@patch("vibe3.commands.status.status")
def test_task_status_check_delegates_check_flag(mock_status) -> None:
    """task status --check should forward the full check shortcut flag."""
    result = runner.invoke(app, ["task", "status", "--check"])

    assert result.exit_code == 0
    mock_status.assert_called_once_with(
        all_flows=False, check=True, json_output=False, trace=False
    )


@patch("vibe3.commands.status.status")
def test_top_level_status_is_hidden_compat_alias(mock_status) -> None:
    """top-level status should still delegate for compatibility."""
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    mock_status.assert_called_once_with(
        all_flows=False, check=False, json_output=False, trace=False
    )


@patch("vibe3.commands.status.status")
def test_top_level_status_check_is_forwarded(mock_status) -> None:
    """top-level compatibility status should accept and forward --check."""
    result = runner.invoke(app, ["status", "--check"])

    assert result.exit_code == 0
    mock_status.assert_called_once_with(
        all_flows=False, check=True, json_output=False, trace=False
    )


@patch("vibe3.commands.status.StatusQueryService")
@patch("vibe3.commands.status.OrchestraStatusService")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status._validate_pid_file")
def test_task_status_groups_orchestration_issues_and_manual_scenes(
    mock_validate_pid,
    mock_flow_service_cls,
    mock_status_service_cls,
    mock_query_service_cls,
) -> None:
    mock_validate_pid.return_value = (12345, True)
    mock_status_service_cls.fetch_live_snapshot.return_value = OrchestraSnapshot(
        timestamp=1700000000.0,
        server_running=False,
        active_issues=(),
        active_flows=2,
        active_worktrees=2,
        queued_issues=(),
    )

    flow_service = MagicMock()
    flow_service.list_flows.return_value = [
        FlowStatusResponse(
            branch="task/issue-320",
            flow_slug="issue-320",
            flow_status="active",
            task_issue_number=320,
        ),
        FlowStatusResponse(
            branch="openai-review",
            flow_slug="openai_review",
            flow_status="active",
            task_issue_number=420,
        ),
    ]
    mock_flow_service_cls.return_value = flow_service

    query_svc = MagicMock()
    query_svc.fetch_orchestrated_issues.return_value = [
        {
            "number": 278,
            "title": "Handoff sample",
            "state": IssueState.HANDOFF,
            "flow": None,
            "queued": False,
        },
        {
            "number": 320,
            "title": "Flow done rule sync",
            "state": IssueState.READY,
            "flow": FlowStatusResponse(
                branch="task/issue-320",
                flow_slug="issue-320",
                flow_status="active",
                task_issue_number=320,
            ),
            "queued": False,
        },
        {
            "number": 372,
            "title": "Webhook blocker",
            "state": IssueState.BLOCKED,
            "flow": None,
            "queued": False,
        },
        {
            "number": 439,
            "title": "Manager backend regression",
            "state": IssueState.FAILED,
            "flow": FlowStatusResponse(
                branch="task/issue-439",
                flow_slug="issue-439",
                flow_status="active",
                task_issue_number=439,
            ),
            "queued": False,
            "failed_reason": "quota exhausted",
        },
    ]
    query_svc.fetch_worktree_map.return_value = {
        "task/issue-320": "issue-320",
        "task/issue-439": "issue-439",
        "openai-review": "wt-openai-review",
    }
    mock_query_service_cls.return_value = query_svc

    with patch("vibe3.clients.git_client.GitClient") as git_cls:
        git = MagicMock()
        git._run.return_value = (
            "worktree /repo/.worktrees/issue-320\n"
            "branch refs/heads/task/issue-320\n\n"
            "worktree /repo/.worktrees/wt-openai-review\n"
            "branch refs/heads/openai-review\n"
        )
        git_cls.return_value = git
        result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    assert "Server: unreachable" in result.stdout
    assert "Issue Progress:" in result.stdout
    assert "Active:" in result.stdout
    assert "Ready Queue:" in result.stdout
    assert "200" not in result.stdout
    assert (
        result.stdout.index("278")
        < result.stdout.index("320")
        < result.stdout.index("372")
    )
    assert "320" in result.stdout
    assert "READY" in result.stdout
    assert "Blocked Issues:" in result.stdout
    assert "372" in result.stdout
    assert "Failed Issues:" in result.stdout
    assert "439" in result.stdout
    assert "quota exhausted" in result.stdout
    assert "Auto Task Scenes:" in result.stdout
    assert "task/issue-320" in result.stdout
    assert "task/issue-320                 wt: issue-320" in result.stdout
    assert "Manual Scenes:" in result.stdout
    assert "openai-review" in result.stdout
    assert "task: #420" in result.stdout
