"""Tests for CheckService PR closed handling."""

from unittest.mock import MagicMock, patch

from vibe3.models.pr import PRState


def _make_check_service():
    """Create a CheckService instance with mocked dependencies."""
    from vibe3.clients import SQLiteClient
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.services.check_service import CheckService

    store = MagicMock(spec=SQLiteClient)
    git_client = MagicMock(spec=GitClient)
    github_client = MagicMock(spec=GitHubClient)

    return CheckService(
        store=store,
        git_client=git_client,
        github_client=github_client,
    )


def test_handle_closed_pr_resets_issue_to_ready() -> None:
    """When PR is closed (not merged), issue should be reset to READY."""
    service = _make_check_service()

    # Mock PR closed (not merged)
    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    # Mock issue links
    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Mock issue state (open)
    service.github_client.view_issue.return_value = {
        "state": "open",
    }

    with patch(
        "vibe3.services.task_resume_operations.TaskResumeOperations"
    ) as mock_resume_ops_cls:
        mock_resume_ops = MagicMock()
        mock_resume_ops_cls.return_value = mock_resume_ops

        result = service._handle_closed_pr("task/issue-456", mock_pr)

        # Verify reset_issue_to_ready was called
        mock_resume_ops.reset_issue_to_ready.assert_called_once()
        call_kwargs = mock_resume_ops.reset_issue_to_ready.call_args[1]
        assert call_kwargs["issue_number"] == 456
        assert call_kwargs["resume_kind"] == "pr_closed"

        # Verify check result is valid
        assert result.is_valid is True


def test_handle_closed_pr_reports_reset_failure() -> None:
    """When reset fails, check should report the closed PR cleanup as invalid."""
    service = _make_check_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
    }

    with patch(
        "vibe3.services.task_resume_operations.TaskResumeOperations"
    ) as mock_resume_ops_cls:
        mock_resume_ops = MagicMock()
        mock_resume_ops.reset_issue_to_ready.side_effect = RuntimeError(
            "scene cleanup failed"
        )
        mock_resume_ops_cls.return_value = mock_resume_ops

        result = service._handle_closed_pr("task/issue-456", mock_pr)

    assert result is not None
    assert result.is_valid is False
    assert result.issues == [
        "Failed to reset issue #456 after PR #123 closed: scene cleanup failed"
    ]


def test_handle_closed_pr_skips_already_closed_issue() -> None:
    """When issue already closed, skip reset."""
    service = _make_check_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Issue already closed on GitHub
    service.github_client.view_issue.return_value = {
        "state": "CLOSED",
    }

    with patch(
        "vibe3.services.task_resume_operations.TaskResumeOperations"
    ) as mock_resume_ops_cls:
        mock_resume_ops = MagicMock()
        mock_resume_ops_cls.return_value = mock_resume_ops

        result = service._handle_closed_pr("task/issue-456", mock_pr)

        # Should not try to reset closed issue
        mock_resume_ops.reset_issue_to_ready.assert_not_called()
        assert result.is_valid is True
