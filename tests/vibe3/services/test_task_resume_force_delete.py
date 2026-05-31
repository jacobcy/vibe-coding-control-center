"""Tests for force_delete strategy based on resume_kind."""

from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations


def test_reset_issue_to_ready_uses_hard_delete_for_pr_closed() -> None:
    """Test that PR closed scenario uses hard delete (force_delete=True)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Mock BlockedStateService
        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_block_cls:
            mock_block_instance = MagicMock()
            mock_block_cls.return_value = mock_block_instance

            # Call with resume_kind="pr_closed"
            operations.reset_issue_to_ready(
                issue_number=1719,
                resume_kind="pr_closed",
                flow=MagicMock(branch="task/issue-1719"),
                repo=None,
                reason="PR #1686 closed without merge",
            )

            # Verify hard delete was used
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-1719",
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=True,  # Key assertion: hard delete for PR closed
            )


def test_reset_issue_to_ready_uses_hard_delete_for_resume_all() -> None:
    """Test that resume all scenario uses hard delete (force_delete=True)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Mock BlockedStateService
        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_block_cls:
            mock_block_instance = MagicMock()
            mock_block_cls.return_value = mock_block_instance

            # Call with resume_kind="all"
            operations.reset_issue_to_ready(
                issue_number=123,
                resume_kind="all",
                flow=MagicMock(branch="task/issue-123"),
                repo=None,
                reason="Resume all issues",
            )

            # Verify hard delete was used
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-123",
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=True,  # Key assertion: hard delete for resume all
            )


def test_reset_issue_to_ready_uses_soft_delete_for_failed() -> None:
    """Test that failed flow scenario uses soft delete (force_delete=False)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Mock BlockedStateService
        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_block_cls:
            mock_block_instance = MagicMock()
            mock_block_cls.return_value = mock_block_instance

            # Call with resume_kind="failed"
            operations.reset_issue_to_ready(
                issue_number=456,
                resume_kind="failed",
                flow=MagicMock(branch="task/issue-456"),
                repo=None,
                reason="Resume failed flow",
            )

            # Verify soft delete was used
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-456",
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=False,  # Key assertion: soft delete for audit trail
            )


def test_reset_issue_to_ready_uses_soft_delete_for_blocked() -> None:
    """Test that blocked flow scenario uses soft delete (force_delete=False)."""
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Mock BlockedStateService
        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_block_cls:
            mock_block_instance = MagicMock()
            mock_block_cls.return_value = mock_block_instance

            # Call with resume_kind="blocked"
            operations.reset_issue_to_ready(
                issue_number=789,
                resume_kind="blocked",
                flow=MagicMock(branch="task/issue-789"),
                repo=None,
                reason="Resume blocked flow",
            )

            # Verify soft delete was used
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-789",
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=False,  # Key assertion: soft delete for audit trail
            )
