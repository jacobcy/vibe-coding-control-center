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


@patch("vibe3.commands.task.TaskService")
def test_task_show_renders_quick_summary(
    mock_task_service_cls,
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
            author="alice",
            body="请优先确认 retry 重入后是否还能直接看懂现场。",
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
    mock_task_service_cls.return_value = task_service

    result = runner.invoke(app, ["task", "show"])

    assert result.exit_code == 0
    output = result.output
    assert "Current Task" in output
    assert "Task:   #123  Task show quick summary" in output
    assert "Latest Work" in output
    assert "notes/report.md" in output
    assert "Latest Instruction" in output
    assert "alice" in output
    assert "PR / CI" in output
    assert "#479" in output
    assert "pending" in output


@patch("vibe3.commands.task.TaskService")
def test_task_show_json_includes_summary_fields(
    mock_task_service_cls,
) -> None:
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
            kind="plan",
            ref="plans/456.md",
            summary="拆出 task show 快速视图字段。",
        ),
        latest_comment=TaskCommentSummary(
            author="reviewer-bot",
            body="请补一个针对 task show 的回归测试。",
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
    payload = json.loads(result.output)
    assert payload["issue_title"] == "JSON summary view"
    assert payload["latest_ref"]["kind"] == "plan"
    assert payload["latest_comment"]["author"] == "reviewer-bot"
    assert payload["pr_summary"]["checks"] == "pass"


@patch("vibe3.commands.task.render_task_comments")
@patch("vibe3.commands.task.TaskService")
def test_task_show_comments_focuses_on_comments_only(
    mock_task_service_cls,
    mock_render_task_comments,
) -> None:
    """task show --comments should reuse the summary and then render comments only."""
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

    result = runner.invoke(app, ["task", "show", "--comments"])

    assert result.exit_code == 0
    mock_render_task_comments.assert_called_once_with(issue_payload)
