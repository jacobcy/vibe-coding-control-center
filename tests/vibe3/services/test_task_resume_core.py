"""Tests for core reset_issue_to_ready operations."""

from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations
from vibe3.models.orchestration import IssueState


def test_reset_issue_to_ready_without_label_deletes_worktree() -> None:
    """Without --label, should call reset_task_scene to delete worktree."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.get_issue_body.return_value = "User content"

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

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

            operations.reset_issue_to_ready(
                issue_number=303,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="test resume",
                label_state=None,  # No --label
            )

            # Verify: unblock was called
            mock_service.unblock.assert_called_once()

            # Verify: cleanup_flow_scene was called (via reset_task_scene)
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once()


def test_reset_issue_to_ready_with_remote_flag() -> None:
    """Test reset_issue_to_ready with remote=True (--remote flag)."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-456"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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

            operations.reset_issue_to_ready(
                issue_number=456,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="test resume with --remote",
                remote=True,  # --remote flag
            )

            # Verify: cleanup called with include_remote=False (keep remote branch)
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-456",
                include_remote=False,  # Key assertion
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=True,
            )
