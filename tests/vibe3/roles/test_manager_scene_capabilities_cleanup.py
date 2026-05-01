"""Unit tests for ManagerSceneCapabilities cleanup methods.

Tests cover:
- cleanup_scene delegates to FlowCleanupService
- cleanup_worktree_only removes worktree without touching branches
- cleanup_branch_only deletes branches
- Error handling for cleanup operations
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.roles.manager_scene_capabilities import ManagerSceneCapabilities


class TestCleanupMethods:
    """Tests for cleanup methods."""

    def test_cleanup_scene_delegates_to_flow_cleanup_service(self) -> None:
        """cleanup_scene delegates to FlowCleanupService.cleanup_flow_scene."""
        mock_cleanup = MagicMock()
        mock_cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        caps = ManagerSceneCapabilities(flow_cleanup_service=mock_cleanup)
        result = caps.cleanup_scene(
            "task/issue-418",
            include_remote=True,
            keep_flow_record=False,
        )

        # Verify delegation
        mock_cleanup.cleanup_flow_scene.assert_called_once_with(
            "task/issue-418",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
            force_delete=False,
        )

        # Verify result structure
        assert result.worktree is True
        assert result.local_branch is True
        assert result.remote_branch is True
        assert result.handoff is True
        assert result.flow_record is True

    def test_cleanup_worktree_only_removes_worktree(self) -> None:
        """cleanup_worktree_only removes worktree without touching branches."""
        mock_git = MagicMock()
        mock_git.find_worktree_path_for_branch.return_value = "/path/to/worktree"
        mock_git.remove_worktree.return_value = None

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.cleanup_worktree_only("task/issue-418")

        assert result is True
        mock_git.find_worktree_path_for_branch.assert_called_once_with("task/issue-418")
        mock_git.remove_worktree.assert_called_once_with(
            "/path/to/worktree", force=True
        )
        # Should NOT delete branches
        mock_git.delete_branch.assert_not_called()

    def test_cleanup_branch_only_deletes_local_branch(self) -> None:
        """cleanup_branch_only deletes local branch."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.delete_branch.return_value = None

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.cleanup_branch_only("task/issue-418", include_remote=False)

        assert result is True
        mock_git.delete_branch.assert_called_once_with("task/issue-418", force=True)

    def test_cleanup_branch_only_includes_remote(self) -> None:
        """cleanup_branch_only deletes remote branch when requested."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.delete_branch.return_value = None
        mock_git._run.return_value = "origin/task/issue-418"
        mock_git.delete_remote_branch.return_value = None

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.cleanup_branch_only("task/issue-418", include_remote=True)

        assert result is True
        mock_git.delete_branch.assert_called_once()
        mock_git.delete_remote_branch.assert_called_once_with("task/issue-418")

    def test_cleanup_worktree_only_returns_true_if_no_worktree(self) -> None:
        """cleanup_worktree_only returns True if worktree doesn't exist."""
        mock_git = MagicMock()
        mock_git.find_worktree_path_for_branch.return_value = None

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.cleanup_worktree_only("task/issue-418")

        assert result is True
        mock_git.remove_worktree.assert_not_called()

    def test_cleanup_worktree_only_returns_false_on_error(self) -> None:
        """cleanup_worktree_only returns False on failure."""
        mock_git = MagicMock()
        mock_git.find_worktree_path_for_branch.return_value = "/path/to/worktree"
        mock_git.remove_worktree.side_effect = Exception("Failed")

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.cleanup_worktree_only("task/issue-418")

        assert result is False

    def test_cleanup_scene_passes_all_options(self) -> None:
        """cleanup_scene passes all options to FlowCleanupService."""
        mock_cleanup = MagicMock()
        mock_cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        caps = ManagerSceneCapabilities(flow_cleanup_service=mock_cleanup)
        caps.cleanup_scene(
            "task/issue-418",
            include_remote=False,
            terminate_sessions=False,
            keep_flow_record=True,
            force_delete=True,
        )

        mock_cleanup.cleanup_flow_scene.assert_called_once_with(
            "task/issue-418",
            include_remote=False,
            terminate_sessions=False,
            keep_flow_record=True,
            force_delete=True,
        )
