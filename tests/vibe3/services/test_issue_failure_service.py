"""Tests for issue_failure_service."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services import issue_failure_service


def test_fail_executor_issue_adds_comment_and_transitions_state() -> None:
    """Test that fail_executor_issue adds comment and transitions to FAILED."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.fail_executor_issue(
            issue_number=123,
            reason="Test failure",
            actor="agent:executor",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 123
        assert "state/failed" in call_args[0][1]
        assert "Test failure" in call_args[0][1]

        mock_labels.confirm_issue_state.assert_called_once_with(
            123,
            IssueState.FAILED,
            actor="agent:executor",
            force=True,
        )


def test_fail_manager_issue_adds_comment_and_transitions_state() -> None:
    """Test that fail_manager_issue adds comment and transitions to FAILED."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.fail_manager_issue(
            issue_number=456,
            reason="Manager failed",
            actor="agent:manager",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 456
        assert "state/failed" in call_args[0][1]
        assert "Manager failed" in call_args[0][1]

        mock_labels.confirm_issue_state.assert_called_once_with(
            456,
            IssueState.FAILED,
            actor="agent:manager",
            force=True,
        )


def test_fail_manager_issue_uses_default_actor() -> None:
    """Test that fail_manager_issue defaults actor to agent:manager."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.fail_manager_issue(
            issue_number=789,
            reason="Default actor test",
        )

        mock_labels.confirm_issue_state.assert_called_once_with(
            789,
            IssueState.FAILED,
            actor="agent:manager",
            force=True,
        )


def test_recover_failed_issue_to_handoff_adds_comment_and_transitions_state() -> None:
    """Test that failed recovery returns to HANDOFF for manager triage."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.recover_failed_issue_to_handoff(
            issue_number=321,
            repo="owner/repo",
            actor="human:recovery",
            reason="manager backend mapping fixed",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 321
        assert "state/handoff" in call_args[0][1]
        assert "manager" in call_args[0][1]
        assert "manager backend mapping fixed" in call_args[0][1]
        assert call_args[1].get("repo") == "owner/repo"

        mock_labels.confirm_issue_state.assert_called_once_with(
            321,
            IssueState.HANDOFF,
            actor="human:recovery",
            force=False,
        )


def test_block_manager_noop_issue_adds_comment_if_missing() -> None:
    """Test that block_manager_noop_issue adds comment if not already present."""
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 999,
        "comments": [],
    }
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.block_manager_noop_issue(
            issue_number=999,
            repo="owner/repo",
            reason="No progress made",
            actor="agent:manager",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 999
        assert "state/blocked" in call_args[0][1]
        assert "No progress made" in call_args[0][1]
        assert call_args[1].get("repo") == "owner/repo"

        mock_labels.confirm_issue_state.assert_called_once_with(
            999,
            IssueState.BLOCKED,
            actor="agent:manager",
            force=True,
        )


def test_block_manager_noop_issue_skips_comment_if_present() -> None:
    """Test that block_manager_noop_issue skips comment if matching one exists."""
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 888,
        "comments": [
            {
                "body": (
                    "[manager] 无法推进,已切换为 state/blocked。\n\n"
                    "原因:No progress made"
                )
            }
        ],
    }
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.block_manager_noop_issue(
            issue_number=888,
            repo="owner/repo",
            reason="No progress made",
            actor="agent:manager",
        )

        mock_github.add_comment.assert_not_called()

        mock_labels.confirm_issue_state.assert_called_once_with(
            888,
            IssueState.BLOCKED,
            actor="agent:manager",
            force=True,
        )


def test_block_manager_noop_issue_handles_none_repo() -> None:
    """Test that block_manager_noop_issue handles None repo parameter."""
    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 777,
        "comments": [],
    }
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.block_manager_noop_issue(
            issue_number=777,
            repo=None,
            reason="Test with None repo",
            actor="agent:manager",
        )

        mock_github.view_issue.assert_called_once_with(777, repo=None)
        mock_github.add_comment.assert_called_once()
        mock_labels.confirm_issue_state.assert_called_once()


def test_resume_failed_issue_to_handoff_adds_comment_and_transitions_state() -> None:
    """Test that failed resume returns to HANDOFF for manager triage."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.resume_failed_issue_to_handoff(
            issue_number=321,
            repo="owner/repo",
            actor="human:resume",
            reason="manager backend mapping fixed",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 321
        assert "state/handoff" in call_args[0][1]
        assert "manager" in call_args[0][1]
        assert "manager backend mapping fixed" in call_args[0][1]
        assert call_args[1].get("repo") == "owner/repo"

        mock_labels.confirm_issue_state.assert_called_once_with(
            321,
            IssueState.HANDOFF,
            actor="human:resume",
            force=False,
        )


def test_resume_failed_issue_to_ready_adds_comment_and_transitions_state() -> None:
    """Test that failed resume returns to READY for fresh manager entry."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.resume_failed_issue_to_ready(
            issue_number=456,
            repo="owner/repo",
            actor="human:resume",
            reason="quota resumed",
        )

        mock_github.add_comment.assert_called_once()
        call_args = mock_github.add_comment.call_args
        assert call_args[0][0] == 456
        assert "state/ready" in call_args[0][1]
        assert "重新进入 manager" in call_args[0][1]
        assert "quota resumed" in call_args[0][1]
        assert call_args[1].get("repo") == "owner/repo"

        mock_labels.confirm_issue_state.assert_called_once_with(
            456,
            IssueState.READY,
            actor="human:resume",
            force=False,
        )


def test_resume_failed_issue_to_ready_uses_default_actor() -> None:
    """Test that resume_failed_issue_to_ready defaults actor to human:resume."""
    mock_github = MagicMock()
    mock_labels = MagicMock()

    with (
        patch.object(issue_failure_service, "GitHubClient", return_value=mock_github),
        patch.object(issue_failure_service, "LabelService", return_value=mock_labels),
    ):
        issue_failure_service.resume_failed_issue_to_ready(
            issue_number=789,
            repo=None,
            reason="manual resume",
        )

        mock_labels.confirm_issue_state.assert_called_once_with(
            789,
            IssueState.READY,
            actor="human:resume",
            force=False,
        )
