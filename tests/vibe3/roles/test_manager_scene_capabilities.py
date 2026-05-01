"""Unit tests for ManagerSceneCapabilities.

Tests cover:
- Observation methods return correct scene state
- Cleanup methods delegate to FlowCleanupService
- Scene status properties work correctly
- Edge cases: missing branch, missing flow, already cleaned
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibe3.roles.manager_scene_capabilities import (
    ManagerSceneCapabilities,
    SceneStatus,
)


class TestSceneStatus:
    """Tests for SceneStatus dataclass."""

    def test_is_terminal_with_done(self) -> None:
        """is_terminal returns True for 'done' status."""
        status = SceneStatus(
            branch="task/issue-418",
            flow_status="done",
            has_worktree=False,
            has_local_branch=False,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=418,
        )
        assert status.is_terminal is True

    def test_is_terminal_with_aborted(self) -> None:
        """is_terminal returns True for 'aborted' status."""
        status = SceneStatus(
            branch="task/issue-418",
            flow_status="aborted",
            has_worktree=False,
            has_local_branch=False,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=418,
        )
        assert status.is_terminal is True

    def test_is_terminal_with_active(self) -> None:
        """is_terminal returns False for 'active' status."""
        status = SceneStatus(
            branch="task/issue-418",
            flow_status="active",
            has_worktree=True,
            has_local_branch=True,
            has_remote_branch=False,
            has_handoff=True,
            issue_number=418,
        )
        assert status.is_terminal is False

    def test_is_terminal_with_none(self) -> None:
        """is_terminal returns False for None status (unmanaged)."""
        status = SceneStatus(
            branch="feature/test",
            flow_status=None,
            has_worktree=True,
            has_local_branch=True,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=None,
        )
        assert status.is_terminal is False

    def test_is_retainable_with_active(self) -> None:
        """is_retainable returns True for active flows."""
        status = SceneStatus(
            branch="task/issue-418",
            flow_status="active",
            has_worktree=True,
            has_local_branch=True,
            has_remote_branch=False,
            has_handoff=True,
            issue_number=418,
        )
        assert status.is_retainable is True

    def test_is_retainable_with_terminal(self) -> None:
        """is_retainable returns False for terminal flows."""
        status = SceneStatus(
            branch="task/issue-418",
            flow_status="done",
            has_worktree=False,
            has_local_branch=False,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=418,
        )
        assert status.is_retainable is False

    def test_is_retainable_unmanaged_with_resources(self) -> None:
        """is_retainable returns True for unmanaged branches with worktree."""
        status = SceneStatus(
            branch="feature/test",
            flow_status=None,
            has_worktree=True,
            has_local_branch=True,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=None,
        )
        assert status.is_retainable is True

    def test_is_retainable_unmanaged_no_resources(self) -> None:
        """is_retainable returns False for unmanaged branches without resources."""
        status = SceneStatus(
            branch="feature/test",
            flow_status=None,
            has_worktree=False,
            has_local_branch=False,
            has_remote_branch=False,
            has_handoff=False,
            issue_number=None,
        )
        assert status.is_retainable is False


class TestManagerSceneCapabilitiesInit:
    """Tests for ManagerSceneCapabilities initialization."""

    def test_init_with_defaults(self) -> None:
        """Can initialize with default clients."""
        caps = ManagerSceneCapabilities()
        assert caps.git_client is not None
        assert caps.store is not None

    def test_init_with_injected_deps(self) -> None:
        """Can initialize with injected dependencies."""
        mock_git = MagicMock()
        mock_store = MagicMock()
        mock_cleanup = MagicMock()
        mock_issue_flow = MagicMock()

        caps = ManagerSceneCapabilities(
            git_client=mock_git,
            store=mock_store,
            flow_cleanup_service=mock_cleanup,
            issue_flow_service=mock_issue_flow,
        )

        assert caps.git_client is mock_git
        assert caps.store is mock_store
        assert caps._flow_cleanup_service is mock_cleanup
        assert caps._issue_flow_service is mock_issue_flow


class TestObservationMethods:
    """Tests for observation methods."""

    @patch("vibe3.services.flow_service.FlowService")
    @patch("vibe3.utils.git_helpers.get_branch_handoff_dir")
    def test_get_scene_status_returns_complete_snapshot(
        self, mock_handoff_dir: MagicMock, mock_flow_service: MagicMock
    ) -> None:
        """get_scene_status returns complete status snapshot."""
        # Setup mocks
        mock_git = MagicMock()
        mock_git.branch_exists.return_value = True
        mock_git.find_worktree_path_for_branch.return_value = "/path/to/worktree"
        mock_git._run.return_value = "origin/task/issue-418"

        mock_store = MagicMock()

        # Mock FlowState
        mock_flow_state = MagicMock()
        mock_flow_state.flow_status = "active"
        mock_flow_service_instance = MagicMock()
        mock_flow_service_instance.get_flow_state.return_value = mock_flow_state
        mock_flow_service.return_value = mock_flow_service_instance

        mock_issue_flow = MagicMock()
        mock_issue_flow.parse_issue_number.return_value = 418

        # Mock handoff directory
        mock_dir = MagicMock()
        mock_dir.exists.return_value = True
        mock_handoff_dir.return_value = mock_dir

        # Execute
        caps = ManagerSceneCapabilities(
            git_client=mock_git,
            store=mock_store,
            issue_flow_service=mock_issue_flow,
        )
        status = caps.get_scene_status("task/issue-418")

        # Verify
        assert status.branch == "task/issue-418"
        assert status.flow_status == "active"
        assert status.has_worktree is True
        assert status.has_local_branch is True
        assert status.has_remote_branch is True
        assert status.has_handoff is True
        assert status.issue_number == 418

    def test_is_flow_terminal_delegates_to_status(self) -> None:
        """is_flow_terminal uses SceneStatus.is_terminal."""
        caps = ManagerSceneCapabilities()
        caps.get_scene_status = MagicMock(
            return_value=SceneStatus(
                branch="task/issue-418",
                flow_status="done",
                has_worktree=False,
                has_local_branch=False,
                has_remote_branch=False,
                has_handoff=False,
                issue_number=418,
            )
        )

        result = caps.is_flow_terminal("task/issue-418")

        assert result is True
        caps.get_scene_status.assert_called_once_with("task/issue-418")

    def test_is_flow_retainable_delegates_to_status(self) -> None:
        """is_flow_retainable uses SceneStatus.is_retainable."""
        caps = ManagerSceneCapabilities()
        caps.get_scene_status = MagicMock(
            return_value=SceneStatus(
                branch="task/issue-418",
                flow_status="active",
                has_worktree=True,
                has_local_branch=True,
                has_remote_branch=False,
                has_handoff=True,
                issue_number=418,
            )
        )

        result = caps.is_flow_retainable("task/issue-418")

        assert result is True
        caps.get_scene_status.assert_called_once_with("task/issue-418")

    def test_has_active_worktree_checks_worktree(self) -> None:
        """has_active_worktree calls _has_worktree helper."""
        mock_git = MagicMock()
        mock_git.find_worktree_path_for_branch.return_value = "/path/to/worktree"

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.has_active_worktree("task/issue-418")

        assert result is True
        mock_git.find_worktree_path_for_branch.assert_called_once_with("task/issue-418")

    def test_has_remote_branch_checks_remote(self) -> None:
        """has_remote_branch calls _has_remote_branch helper."""
        mock_git = MagicMock()
        mock_git._run.return_value = "origin/task/issue-418"

        caps = ManagerSceneCapabilities(git_client=mock_git)
        result = caps.has_remote_branch("task/issue-418")

        assert result is True


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


class TestLazyInitialization:
    """Tests for lazy initialization of services."""

    def test_flow_cleanup_service_lazy_init(self) -> None:
        """FlowCleanupService is initialized lazily."""
        caps = ManagerSceneCapabilities()
        assert caps._flow_cleanup_service is None

        # Access triggers initialization
        service = caps.flow_cleanup_service
        assert service is not None
        assert caps._flow_cleanup_service is service

    def test_issue_flow_service_lazy_init(self) -> None:
        """IssueFlowService is initialized lazily."""
        caps = ManagerSceneCapabilities()
        assert caps._issue_flow_service is None

        # Access triggers initialization
        service = caps.issue_flow_service
        assert service is not None
        assert caps._issue_flow_service is service

    def test_reuses_injected_services(self) -> None:
        """Reuses injected services if provided."""
        mock_cleanup = MagicMock()
        mock_issue_flow = MagicMock()

        caps = ManagerSceneCapabilities(
            flow_cleanup_service=mock_cleanup,
            issue_flow_service=mock_issue_flow,
        )

        # Should return injected instances
        assert caps.flow_cleanup_service is mock_cleanup
        assert caps.issue_flow_service is mock_issue_flow
