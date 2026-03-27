"""Tests for flow create decision behavior."""

from unittest.mock import Mock

from vibe3.services.flow_service import FlowService


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
