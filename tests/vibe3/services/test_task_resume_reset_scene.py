"""Tests for reset_task_scene operation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.vibe3.services.conftest import _make_operations


def test_reset_task_scene_deletes_branch_handoff_and_flow_truth() -> None:
    """Test that reset_task_scene uses FlowCleanupService for complete cleanup."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-329"
    )
    operations.git_client.branch_exists.return_value = True

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

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with correct parameters
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-329",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,  # Resume always deletes flow record
        )


def test_reset_task_scene_creates_tombstone_after_full_rebuild() -> None:
    """Test that reset_task_scene calls cleanup service for tombstone creation."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-999"
    )
    operations.git_client.branch_exists.return_value = True

    branch = "task/issue-999"

    # Mock FlowCleanupService to make test hermetic
    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_class:
        mock_cleanup_service = MagicMock()
        mock_cleanup_class.return_value = mock_cleanup_service

        # Setup cleanup result
        mock_cleanup_service.cleanup_flow_scene.return_value = {
            "tmux_sessions": {"success": True, "sessions": []},
            "worktree": {"success": True, "path": None},
            "local_branch": {"success": True, "deleted": True},
            "remote_branch": {"success": True, "deleted": True},
            "handoff_files": {"success": True, "files": []},
            "flow_record": {"success": True, "deleted": True},
        }

        # Execute reset
        operations.reset_task_scene(branch)

        # Verify cleanup_flow_scene called with correct parameters
        mock_cleanup_service.cleanup_flow_scene.assert_called_once_with(
            branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
        )

        # Note: Tombstone normalization is validated in repository tests
        # This test verifies the call path through FlowCleanupService


def test_reset_task_scene_with_remote_keeps_remote_branch() -> None:
    """Test reset_task_scene with include_remote=False (--remote mode)."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-123"
    )
    operations.git_client.branch_exists.return_value = True

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,  # Though we're keeping it
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Call with include_remote=False (--remote mode)
        operations.reset_task_scene("task/issue-123", include_remote=False)

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with include_remote=False
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=False,  # Key assertion: keep remote branch
            terminate_sessions=True,
            keep_flow_record=False,
        )
