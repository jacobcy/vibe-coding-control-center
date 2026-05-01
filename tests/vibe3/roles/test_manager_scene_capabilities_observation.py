"""Unit tests for ManagerSceneCapabilities observation methods.

Tests cover:
- SceneStatus dataclass properties
- Observation methods return correct scene state
- Initialization with default and injected dependencies
- Lazy initialization of services
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
