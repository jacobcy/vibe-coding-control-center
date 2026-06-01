"""Tests for explicit task scene reset internals."""

from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations


def test_reset_task_scene_uses_hard_delete() -> None:
    """Explicit scene reset is hard-delete-only and no longer task resume default."""
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

        operations.reset_task_scene("task/issue-123", include_remote=True)

        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=True,
        )
