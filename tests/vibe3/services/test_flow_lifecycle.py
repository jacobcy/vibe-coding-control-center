"""Tests for flow lifecycle operations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.services.flow_service import FlowService


class TestFlowLifecycle:
    """Tests for flow close behavior."""

    @staticmethod
    def _build_flow_store(mock_store: Mock) -> None:
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
            "updated_at": "2026-03-26T00:00:00",
        }

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_off_current_branch_before_delete(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing the current worktree branch should switch away before delete."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:main") < actions.index(
            "delete_local:task/current-flow:True"
        )
        mock_store.update_flow_state.assert_called_once_with(
            "task/current-flow",
            flow_status="done",
        )
        mock_store.add_event.assert_called_once_with(
            "task/current-flow",
            "flow_closed",
            "system",
            "Flow closed, branch 'task/current-flow' deleted",
        )

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_to_single_dependent_without_pull(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Single dependent branch should be the switch target without pulling."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = ["task/dependent"]

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:task/dependent") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert not any(action == "run:pull" for action in actions)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_raises_if_current_branch_cannot_switch_away(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Branch close should fail when target missing."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        with pytest.raises(
            RuntimeError, match="Cannot switch away from closing branch"
        ):
            service.close_flow("task/current-flow")

        mock_git.delete_branch.assert_not_called()
        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_does_not_pull_if_post_close_switch_fails(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Post-close switch failure should not pull on an unrelated current branch."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/other"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert "delete_local:task/current-flow:True" in actions
        assert not any(action == "run:pull" for action in actions)


class TestFlowCreateDecision:
    """Tests for flow create access control."""

    def test_active_flow_rejects_create_in_same_worktree(
        self, mock_store: Mock
    ) -> None:
        """Active flow should reject creating new flow in same worktree."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
            "updated_at": "2026-03-26T00:00:00",
        }

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("task/current-flow")

        assert decision.allowed is False
        assert decision.requires_new_worktree is True
        assert "wtnew" in (decision.guidance or "").lower()

    def test_blocked_flow_allows_create_from_current_branch(
        self, mock_store: Mock
    ) -> None:
        """Blocked flow should allow creating downstream flow from current branch."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/blocked-flow",
            "flow_slug": "blocked_flow",
            "flow_status": "blocked",
            "blocked_by": "issue #42",
            "updated_at": "2026-03-26T00:00:00",
        }

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("task/blocked-flow")

        assert decision.allowed is True
        assert decision.start_ref == "task/blocked-flow"
        assert decision.requires_new_worktree is False

    def test_active_flow_waiting_review_allows_create_from_main(
        self, mock_store: Mock
    ) -> None:
        """Active flow with ready PR should allow creating new target."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/reviewing-flow",
            "flow_slug": "reviewing_flow",
            "flow_status": "active",
            "pr_ready_for_review": 1,
            "updated_at": "2026-03-26T00:00:00",
        }

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("task/reviewing-flow")

        assert decision.allowed is True
        assert decision.start_ref == "origin/main"
        assert decision.requires_new_worktree is False

    def test_done_flow_can_start_new_target_from_safe_base(
        self, mock_store: Mock
    ) -> None:
        """Done flow should allow starting new target from safe base."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/done-flow",
            "flow_slug": "done_flow",
            "flow_status": "done",
            "updated_at": "2026-03-26T00:00:00",
        }

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("task/done-flow")

        assert decision.allowed is True
        assert decision.start_ref == "origin/main"
        assert decision.requires_new_worktree is False

    def test_no_flow_allows_create_from_main(self, mock_store: Mock) -> None:
        """No existing flow should allow creating new flow from main."""
        mock_store.get_flow_state.return_value = None

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("main")

        assert decision.allowed is True
        assert decision.start_ref == "origin/main"
        assert decision.requires_new_worktree is False

    def test_aborted_flow_allows_new_target(self, mock_store: Mock) -> None:
        """Aborted flow should allow starting new target."""
        mock_store.get_flow_state.return_value = {
            "branch": "task/aborted-flow",
            "flow_slug": "aborted_flow",
            "flow_status": "aborted",
            "updated_at": "2026-03-26T00:00:00",
        }

        service = FlowService(store=mock_store)
        decision = service.can_create_from_current_worktree("task/aborted-flow")

        assert decision.allowed is True
        assert decision.start_ref == "origin/main"
