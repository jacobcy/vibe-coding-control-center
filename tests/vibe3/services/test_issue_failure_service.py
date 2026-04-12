"""Tests for issue failure/block side effects."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.issue_failure_service import (
    block_manager_noop_issue,
    block_planner_noop_issue,
    fail_manager_issue,
    resume_failed_issue_to_ready,
)


@patch("vibe3.services.issue_failure_service.LabelService")
@patch("vibe3.services.issue_failure_service.GitHubClient")
def test_fail_manager_issue_comments_and_forces_failed_state(
    mock_github_class, mock_label_service_class
) -> None:
    mock_github = MagicMock()
    mock_github_class.return_value = mock_github
    mock_label_service = MagicMock()
    mock_label_service_class.return_value = mock_label_service

    fail_manager_issue(issue_number=42, reason="boom")

    mock_github.add_comment.assert_called_once_with(
        42,
        "[manager] 管理执行报错,已切换为 state/failed。\n\n原因:boom",
        repo=None,
    )
    mock_label_service.confirm_issue_state.assert_called_once_with(
        42,
        IssueState.FAILED,
        actor="agent:manager",
        force=True,
    )


@patch("vibe3.services.issue_failure_service.LabelService")
@patch("vibe3.services.issue_failure_service.GitHubClient")
def test_block_manager_noop_issue_dedupes_matching_reason(
    mock_github_class, mock_label_service_class
) -> None:
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "comments": [
            {"body": "[manager] 无法推进,已切换为 state/blocked。\n\n原因:same"}
        ]
    }
    mock_github_class.return_value = mock_github
    mock_label_service = MagicMock()
    mock_label_service_class.return_value = mock_label_service

    block_manager_noop_issue(
        issue_number=7,
        repo="owner/repo",
        reason="same",
        actor="agent:manager",
    )

    mock_github.add_comment.assert_not_called()
    mock_label_service.confirm_issue_state.assert_called_once_with(
        7,
        IssueState.BLOCKED,
        actor="agent:manager",
        force=True,
    )


@patch("vibe3.services.issue_failure_service.LabelService")
@patch("vibe3.services.issue_failure_service.GitHubClient")
def test_block_planner_noop_issue_uses_latest_comment_deduping(
    mock_github_class, mock_label_service_class
) -> None:
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "comments": [
            {
                "body": (
                    "[plan] 规划执行完成，但未登记 authoritative plan_ref，"
                    "已切换为 state/blocked。\n\n原因:missing"
                )
            }
        ]
    }
    mock_github_class.return_value = mock_github
    mock_label_service = MagicMock()
    mock_label_service_class.return_value = mock_label_service

    block_planner_noop_issue(issue_number=8, reason="missing", repo="owner/repo")

    mock_github.add_comment.assert_not_called()
    mock_label_service.confirm_issue_state.assert_called_once_with(
        8,
        IssueState.BLOCKED,
        actor="agent:plan",
        force=True,
    )


@patch("vibe3.services.issue_failure_service.LabelService")
@patch("vibe3.services.issue_failure_service.GitHubClient")
def test_resume_failed_issue_to_ready_dedupes_latest_comment_only(
    mock_github_class, mock_label_service_class
) -> None:
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "comments": [
            {
                "body": (
                    "[resume] 已从 state/failed 继续到 state/ready。\n\n"
                    "将重新进入 manager 标准入口。"
                )
            }
        ]
    }
    mock_github_class.return_value = mock_github
    mock_label_service = MagicMock()
    mock_label_service_class.return_value = mock_label_service

    resume_failed_issue_to_ready(issue_number=9, repo="owner/repo", reason="")

    mock_github.add_comment.assert_not_called()
    mock_label_service.confirm_issue_state.assert_called_once_with(
        9,
        IssueState.READY,
        actor="human:resume",
        force=True,
    )
