"""Tests for reset_task_scene operation.

Task resume always hard deletes (force_delete=True).
Soft delete is only for vibe3 check (issue closed / flow aborted).
"""

from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations


def test_reset_task_scene_hard_deletes_by_default() -> None:
    """reset_task_scene always uses hard delete (force_delete=True)."""
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

        operations.reset_task_scene("task/issue-329")

        mock_cleanup_cls.assert_called_once()
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-329",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,
        )


def test_reset_task_scene_with_remote_keeps_remote_branch() -> None:
    """reset_task_scene with include_remote=False keeps remote branch."""
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

        operations.reset_task_scene("task/issue-123", include_remote=False)

        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,
        )
