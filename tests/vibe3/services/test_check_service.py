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


def test_handle_closed_pr_blocks_issue_state_with_comment() -> None:
    """When PR is closed (not merged), issue should be blocked with guidance comment."""
    service = _make_check_service()

    # Mock PR closed (not merged)
    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    # Mock flow state exists
    service.store.get_flow_state.return_value = {
        "branch": "task/issue-456",
        "flow_status": "active",
        "latest_actor": "agent:test",
    }

    # Mock issue links
    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Mock issue state
    service.github_client.view_issue.return_value = {
        "state": "open",
        "labels": [{"name": "state/in-progress"}],
    }

    with patch.object(service._flow_status_service, "mark_flow_aborted") as mock_abort:
        with patch.object(service, "_block_issue_for_pr_closed") as mock_block:
            result = service._handle_closed_pr("task/issue-456", mock_pr)

    # Verify flow marked aborted
    mock_abort.assert_called_once()

    # Verify issue blocked with comment
    mock_block.assert_called_once_with("task/issue-456", 123)

    # Verify check result is valid
    assert result.is_valid is True


def test_handle_closed_pr_skips_already_closed_issue() -> None:
    """When issue already closed, skip blocking."""
    service = _make_check_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED

    service.store.get_flow_state.return_value = {
        "branch": "task/issue-456",
        "flow_status": "active",
    }
    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Issue already closed on GitHub
    service.github_client.view_issue.return_value = {
        "state": "CLOSED",
    }

    with patch.object(service._flow_status_service, "mark_flow_aborted"):
        result = service._handle_closed_pr("task/issue-456", mock_pr)

    # Should not try to block closed issue
    # Check that no label transition was attempted
    assert result.is_valid is True


def test_block_issue_for_pr_closed_adds_guidance_comment() -> None:
    """Blocking issue should add helpful guidance comment."""
    service = _make_check_service()

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
    }

    with patch("vibe3.services.label_service.LabelService") as mock_label_cls:
        mock_label = MagicMock()
        mock_label_cls.return_value = mock_label

        service._block_issue_for_pr_closed("task/issue-456", pr_number=123)

    # Verify comment added
    service.github_client.add_comment.assert_called_once()
    call_args = service.github_client.add_comment.call_args
    assert call_args[0][0] == 456  # issue_number

    comment_body = call_args[0][1]
    assert "PR #123" in comment_body
    assert "已关闭" in comment_body
    assert "follow-up issue" in comment_body.lower()
    assert (
        "vibe task resume" in comment_body.lower()
        or "vibe check --clean-branch" in comment_body.lower()
    )
