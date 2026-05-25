"""Tests for task binding - flow bind and pr task guidance.

Merged from test_task_hints.py + test_task_management_bind.py.
"""

import json
from unittest.mock import MagicMock, call, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.flow import app as flow_app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner(env={"NO_COLOR": "1"})


# ==============================================================================
# Task hint tests (from test_task_hints.py)
# ==============================================================================


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.commands.flow_status.find_parent_branch", return_value=None)
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_warns_when_task_issue_missing(
    mock_service_cls, _find_parent_branch, _render_timeline
) -> None:
    """flow show should suggest binding a task when none is present."""
    mock_service = MagicMock()
    mock_service.get_current_branch.return_value = "task/demo"
    flow_status = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    mock_service.get_flow_status.return_value = flow_status
    mock_service.get_flow_timeline.return_value = {
        "state": flow_status,
        "events": [],
    }
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    assert "还没有 task" in result.stdout
    assert "vibe3 flow bind <issue> --role task" in result.stdout


@patch("vibe3.commands.pr_create.PRService")
@patch("vibe3.commands.pr_create.FlowService")
def test_pr_create_requires_human_confirmation(
    mock_flow_service_cls, mock_pr_service_cls
) -> None:
    """pr create should exit with human confirmation warning by default."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    mock_flow_service_cls.return_value = flow_service

    mock_pr_service = MagicMock()
    mock_pr_service.get_open_pr_for_branch.return_value = None
    mock_pr_service_cls.return_value = mock_pr_service

    result = runner.invoke(app, ["pr", "create", "-t", "Test PR"])

    # New behavior: exits with 0 and shows human-only warning
    assert result.exit_code == 0
    assert "此命令需要明确确认" in result.output
    assert "--yes" in result.output
    assert "--agent" in result.output
    mock_pr_service.create_pr.assert_not_called()


@patch("vibe3.commands.pr_create.check_branch_behind", return_value=None)
@patch("vibe3.commands.pr_create.render_pr_created")
@patch("vibe3.commands.pr_create.PRService")
@patch("vibe3.commands.pr_create.FlowService")
def test_pr_create_allows_yes_when_task_issue_missing(
    mock_flow_service_cls, mock_pr_service_cls, _render_pr_created, _check_behind
) -> None:
    """pr create --yes should bypass gates."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_status = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service.get_flow_status.return_value = flow_status
    mock_flow_service_cls.return_value = flow_service

    mock_pr_service = MagicMock()
    mock_pr_service.get_open_pr_for_branch.return_value = None
    mock_pr_service.create_pr.return_value = MagicMock(model_dump=lambda: {})
    mock_pr_service_cls.return_value = mock_pr_service

    result = runner.invoke(app, ["pr", "create", "-t", "Test PR", "--yes"])

    assert result.exit_code == 0
    mock_pr_service.create_pr.assert_called_once()


@patch("vibe3.commands.pr_query.FlowService")
@patch("vibe3.commands.pr_query.PRService")
def test_pr_show_missing_pr_includes_bind_hint(
    mock_pr_service_cls, mock_flow_service_cls
) -> None:
    """pr show should include bind hint when current flow has no task."""
    # Mock git_client
    git_client = MagicMock()
    git_client.get_current_branch.return_value = "task/demo"

    pr_service = MagicMock()
    pr_service.git_client = git_client
    pr_service.get_pr.return_value = None
    pr_service.get_branch_pr_status.return_value = None
    mock_pr_service_cls.return_value = pr_service

    # Mock FlowService to return flow status without task_issue_number
    flow_service = MagicMock()
    flow_status = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    flow_service.get_flow_status.return_value = flow_status
    mock_flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["pr", "show"])

    assert result.exit_code == 1
    assert "No PR found for current branch 'task/demo'" in result.output
    assert "vibe3 flow bind <issue> --role task" in result.output


# ==============================================================================
# Flow bind role semantics tests (from test_task_management_bind.py)
# ==============================================================================


def test_flow_bind_supports_related_role() -> None:
    """Test flow bind successfully binds a task to the current flow."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "219"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 219, "task", actor=None
    )


def test_flow_bind_with_task_role() -> None:
    """flow bind 220 --role task should bind as task."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "220", "--role", "task"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 220, "task", actor=None
    )


def test_flow_bind_with_related_role() -> None:
    """flow bind 219 --role related should bind as related."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "219", "--role", "related"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/demo", 219, "related", actor=None
    )


def test_flow_bind_dependency_delegates_without_direct_link_issue() -> None:
    """flow bind 218 --role dependency should only use blocked compatibility logic."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "218", "--role", "dependency"])

    assert result.exit_code == 0
    task_service.link_issue.assert_not_called()
    flow_service.block_flow.assert_called_once_with(
        "task/demo", blocked_by_issue=218, actor=None
    )


def test_flow_bind_dependency_json_output_single_ref() -> None:
    """dependency compatibility path should keep single-item JSON output shape."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app, ["bind", "218", "--role", "dependency", "--json"]
            )

    assert result.exit_code == 0
    # Deprecated --json flag should produce warning in stderr
    assert "Warning: --json is deprecated, use --format json instead" in result.stderr
    task_service.link_issue.assert_not_called()
    payload = json.loads(result.stdout)
    assert payload["branch"] == "task/demo"
    assert payload["issue_number"] == 218
    assert payload["issue_role"] == "dependency"
    assert isinstance(payload["created_at"], str)


def test_flow_bind_dependency_json_output_multiple_refs() -> None:
    """dependency compatibility path should keep list JSON output for multiple refs."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app,
                ["bind", "218", "219", "--role", "dependency", "--json"],
            )

    assert result.exit_code == 0
    # Deprecated --json flag should produce warning in stderr
    assert "Warning: --json is deprecated, use --format json instead" in result.stderr
    task_service.link_issue.assert_not_called()
    payload = json.loads(result.stdout)
    assert payload == [
        {
            "branch": "task/demo",
            "issue_number": 218,
            "issue_role": "dependency",
            "created_at": payload[0]["created_at"],
        },
        {
            "branch": "task/demo",
            "issue_number": 219,
            "issue_role": "dependency",
            "created_at": payload[1]["created_at"],
        },
    ]
    assert all(isinstance(item["created_at"], str) for item in payload)
    flow_service.block_flow.assert_has_calls(
        [
            call("task/demo", blocked_by_issue=218, actor=None),
            call("task/demo", blocked_by_issue=219, actor=None),
        ]
    )


def test_flow_bind_dependency_stdout_output_non_json() -> None:
    """dependency compatibility path should keep legacy stdout messaging."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "218", "--role", "dependency"])

    assert result.exit_code == 0
    task_service.link_issue.assert_not_called()
    assert "Issue #218 linked as dependency to flow task/demo" in result.stdout


def test_flow_bind_with_explicit_branch_option() -> None:
    """flow bind --branch task/other 219 should bind to the specified branch."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service.get_current_branch.return_value = "task/demo"
        flow_service.get_flow_status.return_value = MagicMock()
        flow_service._is_main_branch.return_value = False
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "--branch", "task/other", "219"])

    assert result.exit_code == 0
    task_service.link_issue.assert_called_once_with(
        "task/other", 219, "task", actor=None
    )


def test_flow_bind_with_explicit_protected_branch_fails() -> None:
    """flow bind --branch main should fail before linking issues."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service._is_main_branch.return_value = True
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(flow_app, ["bind", "--branch", "main", "219"])

    assert result.exit_code != 0
    task_service.link_issue.assert_not_called()


def test_flow_bind_with_explicit_missing_flow_fails() -> None:
    """flow bind --branch task/missing should fail when the flow does not exist."""
    with patch(
        "vibe3.commands.flow_manage.TaskService", create=True
    ) as task_service_cls:
        task_service = MagicMock()
        task_service_cls.return_value = task_service

        flow_service = MagicMock()
        flow_service._is_main_branch.return_value = False
        flow_service.get_flow_status.return_value = None
        with patch("vibe3.commands.flow_manage.FlowService", return_value=flow_service):
            result = runner.invoke(
                flow_app, ["bind", "--branch", "task/missing", "219"]
            )

    assert result.exit_code != 0
    task_service.link_issue.assert_not_called()
