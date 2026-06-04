"""Tests for the task show quick summary view."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.task_service import (
    TaskCommentSummary,
    TaskPRSummary,
    TaskRefSummary,
    TaskShowResult,
)

runner = CliRunner(env={"NO_COLOR": "1"})


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_renders_quick_summary(
    mock_task_service_cls, mock_render_task_comments
) -> None:
    """task show should present a compact scene summary at a glance."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-123"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-123",
        local_task=FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="summary-view",
            flow_status="active",
            task_issue_number=123,
            spec_ref="specs/123.md",
            next_step="复核 reviewer block 行为",
        ),
        related_issue_numbers=[301],
        dependency_issue_numbers=[302],
        issue_title="Task show quick summary",
        issue_state="OPEN",
        latest_ref=TaskRefSummary(
            kind="report",
            ref="notes/report.md",
            summary="上一轮已经收敛到 reviewer 前的实现，待复核。",
        ),
        latest_human_instruction=TaskCommentSummary(
            author="alice", body="请优先确认 retry 重入后是否还能直接看懂现场。"
        ),
        pr_summary=TaskPRSummary(
            number=479,
            title="Add task summary view",
            state="open",
            draft=True,
            url="https://example.com/pr/479",
            checks="pending",
        ),
    )
    task_service.fetch_issue_with_comments.return_value = None
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show"])
    assert result.exit_code == 0
    output = result.output
    assert "Current Task" in output
    assert "Task:   #123  Task show quick summary" in output
    assert "Latest Work" in output
    # After refactor: ref displayed as handoff command, not path
    assert "vibe3 handoff show" in output
    assert "@report" in output
    assert "PR / CI" in output
    assert "#479" in output
    assert "pending" in output


@patch("vibe3.commands.task.TaskService")
def test_task_show_json_includes_summary_fields(mock_task_service_cls) -> None:
    """task show --json should expose the same summary contract."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-456"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-456",
        local_task=FlowStatusResponse(
            branch="task/issue-456",
            flow_slug="summary-json",
            flow_status="active",
            task_issue_number=456,
        ),
        issue_title="JSON summary view",
        latest_ref=TaskRefSummary(
            kind="plan", ref="plans/456.md", summary="拆出 task show 快速视图字段。"
        ),
        latest_comment=TaskCommentSummary(
            author="reviewer-bot", body="请补一个针对 task show 的回归测试。"
        ),
        pr_summary=TaskPRSummary(
            number=500,
            title="Expose task show summary JSON",
            state="open",
            draft=False,
            url="https://example.com/pr/500",
            checks="pass",
        ),
    )
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["issue_title"] == "JSON summary view"
    assert payload["latest_ref"]["kind"] == "plan"
    assert payload["latest_comment"]["author"] == "reviewer-bot"
    assert payload["pr_summary"]["checks"] == "pass"


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_always_renders_comments(
    mock_task_service_cls, mock_render_task_comments
) -> None:
    """task show should always render comments (no --comments flag needed)."""
    issue_payload = {
        "number": 123,
        "title": "Task show quick summary",
        "body": "这段 issue body 不该成为 comments 视图的主角。",
        "comments": [
            {
                "author": {"login": "alice"},
                "body": "请直接看最新评论，不用再展示 issue body。",
            }
        ],
    }
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-123"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-123",
        local_task=FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="summary-view",
            flow_status="active",
            task_issue_number=123,
        ),
    )
    task_service.fetch_issue_with_comments.return_value = issue_payload
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show"])
    assert result.exit_code == 0
    mock_render_task_comments.assert_called_once_with(issue_payload)


@patch("vibe3.commands.task.TaskService")
def test_task_show_format_json(mock_task_service_cls) -> None:
    """task show --format json should output JSON."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-456"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-456",
        local_task=FlowStatusResponse(
            branch="task/issue-456",
            flow_slug="format-test",
            flow_status="active",
            task_issue_number=456,
        ),
        issue_title="Format test",
    )
    mock_task_service_cls.return_value = task_service
    result = runner.invoke(app, ["task", "show", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["issue_title"] == "Format test"


@patch("vibe3.commands.task.TaskService")
def test_task_show_format_yaml(mock_task_service_cls) -> None:
    """task show --format yaml should output YAML."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-456"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-456",
        local_task=FlowStatusResponse(
            branch="task/issue-456",
            flow_slug="format-test",
            flow_status="active",
            task_issue_number=456,
        ),
        issue_title="Format test",
    )
    mock_task_service_cls.return_value = task_service
    result = runner.invoke(app, ["task", "show", "--format", "yaml"])
    assert result.exit_code == 0
    assert "branch: task/issue-456" in result.output
    assert "issue_title: Format test" in result.output


@patch("vibe3.commands.task.TaskService")
def test_task_show_deprecated_json_flag(mock_task_service_cls) -> None:
    """task show --json should show deprecation warning."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-456"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-456",
        local_task=FlowStatusResponse(
            branch="task/issue-456",
            flow_slug="format-test",
            flow_status="active",
            task_issue_number=456,
        ),
        issue_title="Format test",
    )
    mock_task_service_cls.return_value = task_service
    result = runner.invoke(app, ["task", "show", "--json"])
    assert result.exit_code == 0
    assert "deprecated" in result.stderr.lower()
    payload = json.loads(result.stdout)
    assert payload["issue_title"] == "Format test"


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_full_flag(mock_task_service_cls, mock_render_task_comments) -> None:
    """task show --full should show complete summary without truncation."""
    long_summary = "\n".join([f"Line {i}" for i in range(10)])
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-123"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-123",
        local_task=FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="full-test",
            flow_status="active",
            task_issue_number=123,
        ),
        latest_ref=TaskRefSummary(
            kind="report", ref="notes/report.md", summary=long_summary
        ),
    )
    task_service.fetch_issue_with_comments.return_value = None
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show"])
    assert result.exit_code == 0
    assert "Line 0" in result.output
    assert "Line 2" in result.output
    assert "Line 3" not in result.output  # Should be truncated

    result_full = runner.invoke(app, ["task", "show", "--full"])
    assert result_full.exit_code == 0
    for i in range(10):
        assert f"Line {i}" in result_full.output


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_renders_multiple_tasks(
    mock_task_service_cls, mock_render_task_comments
) -> None:
    """task show should display multiple task issues with primary label."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-123"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-123",
        local_task=FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="multi-task",
            flow_status="active",
            task_issue_number=123,
        ),
        task_issue_numbers=[123, 456, 789],
        issue_title="Primary task title",
        issue_state="OPEN",
    )
    task_service.fetch_issue_with_comments.return_value = None
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show"])
    assert result.exit_code == 0
    output = result.output
    assert "Task Issue(s):" in output
    assert "#123  (primary)  Primary task title" in output
    assert "#456" in output
    assert "#789" in output


@patch("vibe3.commands.task.TaskService")
def test_task_show_json_includes_task_issue_numbers(mock_task_service_cls) -> None:
    """task show --json should include task_issue_numbers array."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-123"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-123",
        local_task=FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="multi-task-json",
            flow_status="active",
            task_issue_number=123,
        ),
        task_issue_numbers=[123, 456],
        issue_title="Multi-task JSON test",
    )
    mock_task_service_cls.return_value = task_service
    result = runner.invoke(app, ["task", "show", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["task_issue_numbers"] == [123, 456]


# Tests for issue number without local flow


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_issue_no_flow_renders_issue_info(
    mock_task_service_cls, mock_render_task_comments
) -> None:
    """task show <issue> with no local flow should render remote issue info."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "999"
    task_service.show_task.return_value = TaskShowResult(
        branch="999",
        local_task=None,
        issue_title="Remote issue without local flow",
        issue_state="OPEN",
    )
    task_service.fetch_issue_with_comments.return_value = None
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show", "999"])
    assert result.exit_code == 0
    output = result.output
    assert "Remote issue #999 (no local flow)" in output
    assert "Title:  Remote issue without local flow" in output
    assert "State:  open" in output
    assert "[yellow]" not in output


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_issue_with_flow_resolves_to_branch(
    mock_task_service_cls, mock_render_task_comments
) -> None:
    """task show <issue> with existing active flow should show normal task view."""
    task_service = MagicMock()
    task_service.resolve_branch.return_value = "task/issue-999"
    task_service.show_task.return_value = TaskShowResult(
        branch="task/issue-999",
        local_task=FlowStatusResponse(
            branch="task/issue-999",
            flow_slug="issue-999",
            flow_status="active",
            task_issue_number=999,
        ),
        issue_title="Issue with active flow",
        issue_state="OPEN",
    )
    task_service.fetch_issue_with_comments.return_value = None
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show", "999"])
    assert result.exit_code == 0
    output = result.output
    assert "Current Task" in output
    assert "Branch: task/issue-999" in output
    assert "Remote issue" not in output


@patch("vibe3.commands.task.TaskService")
def test_task_show_issue_all_aborted_raises_error(mock_task_service_cls) -> None:
    """task show <issue> with only aborted flows should exit with error."""
    task_service = MagicMock()
    from vibe3.exceptions import UserError

    task_service.resolve_branch.side_effect = UserError(
        "All flows for issue #999 are aborted:\n"
        "  - task/issue-999 (status: aborted, pr: none)\n\n"
        "Use 'vibe3 flow restore <branch>' to reactivate a flow."
    )
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show", "999"])
    assert result.exit_code == 1
    output = result.output
    assert "Error:" in output
    assert "All flows for issue #999 are aborted" in output
