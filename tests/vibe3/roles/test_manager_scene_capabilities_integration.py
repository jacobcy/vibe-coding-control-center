"""Integration tests for ManagerSceneCapabilities.

Tests cover:
- Edge cases: missing branch, missing flow, already cleaned
- Error handling for observation and cleanup operations
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibe3.roles.manager_scene_capabilities import ManagerSceneCapabilities


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("vibe3.services.flow_service.FlowService")
    @patch("vibe3.utils.git_helpers.get_branch_handoff_dir")
    def test_get_scene_status_handles_missing_flow(
        self, mock_handoff_dir: MagicMock, mock_flow_service: MagicMock
    ) -> None:
        """get_scene_status handles branches without flow records."""
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.find_worktree_path_for_branch.return_value = None
        mock_git._run.return_value = ""

        mock_store = MagicMock()

        mock_flow_service_instance = MagicMock()
        mock_flow_service_instance.get_flow_state.return_value = None
        mock_flow_service.return_value = mock_flow_service_instance

        mock_issue_flow = MagicMock()
        mock_issue_flow.parse_issue_number.return_value = None

        # Mock handoff directory
        mock_dir = MagicMock()
        mock_dir.exists.return_value = False
        mock_handoff_dir.return_value = mock_dir

        caps = ManagerSceneCapabilities(
            git_client=mock_git,
            store=mock_store,
            issue_flow_service=mock_issue_flow,
        )
        status = caps.get_scene_status("feature/test")

        assert status.flow_status is None
        assert status.issue_number is None

    def test_has_remote_branch_returns_false_on_error(self) -> None:
        """has_remote_branch returns False on Git error."""
        mock_git = MagicMock()
        mock_git._run.side_effect = Exception("Git error")

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.has_remote_branch("task/issue-418")

        assert result is False

    def test_has_active_worktree_returns_false_on_error(self) -> None:
        """has_active_worktree returns False on Git error."""
        mock_git = MagicMock()
        mock_git.find_worktree_path_for_branch.side_effect = Exception("Git error")

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.has_active_worktree("task/issue-418")

        assert result is False
