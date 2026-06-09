"""Tests for FlowService core operations."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow_service import FlowService


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def mock_git():
    return MagicMock()


class TestFlowServiceCreate:
    """Tests for create_flow."""

    def test_create_flow_with_initiated_by(self, mock_store, mock_git):
        service = FlowService(store=mock_store, git_client=mock_git)
        mock_git.get_current_branch.return_value = "feature/test"

        # No tombstone exists
        mock_store.get_flow_state_include_deleted.return_value = None

        # First call (idempotency check) returns None; subsequent calls
        # return the created state.
        mock_store.get_flow_state.side_effect = [
            None,
            {
                "branch": "feature/test",
                "flow_slug": "test-flow",
                "flow_status": "active",
                "updated_at": "2026-04-01T00:00:00",
                "initiated_by": "manual",
            },
        ]
        mock_store.get_issue_links.return_value = []

        with patch("vibe3.services.flow.read_mixin.GitHubClient") as mock_gh:
            mock_gh.return_value.get_pr.return_value = None

            status = service.create_flow(
                slug="test-flow", branch="feature/test", initiated_by="manual"
            )

        assert status.initiated_by == "manual"
        mock_store.update_flow_state.assert_called_once()
        args, kwargs = mock_store.update_flow_state.call_args
        assert kwargs["initiated_by"] == "manual"
        assert kwargs["flow_slug"] == "test-flow"

    def test_create_flow_restores_tombstone_row(self, mock_store, mock_git):
        """create_flow must restore and reactivate a soft-deleted tombstone row.

        After restoration, the idempotency check is skipped so the normal
        create path runs: update_flow_state with slug/actor/initiated_by,
        add_event for flow_created, and get_flow_status for the return value.
        """
        service = FlowService(store=mock_store, git_client=mock_git)
        mock_git.get_current_branch.return_value = "task/issue-123"

        # Simulate tombstone: get_flow_state_include_deleted finds the
        # soft-deleted row with deleted_at set.
        tombstone = {
            "branch": "task/issue-123",
            "flow_slug": "issue-123",
            "flow_status": "aborted",
            "deleted_at": "2026-05-27T00:00:00",
            "updated_at": "2026-05-27T00:00:00",
        }
        mock_store.get_flow_state_include_deleted.return_value = tombstone

        # Normal create path calls get_flow_status which internally calls
        # get_flow_state. Return the active flow for that chain.
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-123",
            "flow_slug": "issue-123",
            "flow_status": "active",
            "updated_at": "2026-05-27T18:00:00",
            "initiated_by": "manual",
        }
        mock_store.get_issue_links.return_value = []
        mock_git.find_worktree_path_for_branch.return_value = None

        with patch("vibe3.services.flow.read_mixin.GitHubClient") as mock_gh:
            mock_gh.return_value.get_pr.return_value = None

            status = service.create_flow(
                slug="issue-123", branch="task/issue-123", initiated_by="manual"
            )

        assert status is not None
        # Must have called restore_flow
        mock_store.restore_flow.assert_called_once_with("task/issue-123")
        # Must have reset flow_status to 'active' (tombstone reactivation)
        update_calls = mock_store.update_flow_state.call_args_list
        status_updates = [
            c for c in update_calls if c.kwargs.get("flow_status") == "active"
        ]
        assert len(status_updates) >= 1
        # Normal create path must record flow_created event
        mock_store.add_event.assert_called_once()
        add_event_args = mock_store.add_event.call_args[0]
        assert add_event_args[0] == "task/issue-123"
        assert add_event_args[1] == "flow_created"


class TestFlowServiceAbort:
    """Tests for abort_flow."""

    def test_abort_flow_marks_flow_status_aborted(self, mock_store, mock_git):
        """Test abort_flow sets flow_status to aborted."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.abort_flow(
            branch="task/issue-123",
            reason="Task no longer needed",
            actor="agent:manager",
        )

        mock_store.update_flow_state.assert_called_once()
        args, kwargs = mock_store.update_flow_state.call_args
        assert kwargs["flow_status"] == "aborted"

    def test_abort_flow_records_flow_aborted_event(self, mock_store, mock_git):
        """Test abort_flow records flow_aborted event."""
        service = FlowService(store=mock_store, git_client=mock_git)

        service.abort_flow(
            branch="task/issue-456",
            reason="Invalid task",
            actor="agent:manager",
        )

        mock_store.add_event.assert_called_once()
        args, kwargs = mock_store.add_event.call_args
        assert args[0] == "task/issue-456"
        assert args[1] == "flow_aborted"
        assert args[2] == "agent:manager"
        assert "Invalid task" in args[3]

    def test_aborted_flow_can_be_reactivated_later(self, mock_store, mock_git):
        """Test aborted flow can be reactivated."""
        service = FlowService(store=mock_store, git_client=mock_git)

        # Mock an aborted flow with flow_slug
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-789",
            "flow_status": "aborted",
            "flow_slug": "issue-789",
        }

        # Reactivate should work
        service.reactivate_flow("task/issue-789")

        # Verify flow_status is updated to active
        update_calls = mock_store.update_flow_state.call_args_list
        assert len(update_calls) > 0
        # Check the last update_flow_state call
        last_update = update_calls[-1]
        _, kwargs = last_update
        assert kwargs.get("flow_status") == "active"

    def test_aborted_flow_reactivation_preserves_refs(self, mock_store, mock_git):
        """Test reactivating aborted flow preserves refs and events."""
        service = FlowService(store=mock_store, git_client=mock_git)

        # Mock an aborted flow with historical refs
        mock_store.get_flow_state.return_value = {
            "branch": "task/issue-999",
            "flow_status": "aborted",
            "flow_slug": "issue-999",
            "plan_ref": "docs/plans/old-plan.md",  # Historical ref
            "spec_ref": "docs/specs/old-spec.md",  # Should be preserved
        }

        service.reactivate_flow("task/issue-999")

        # Verify update_flow_state was called
        assert mock_store.update_flow_state.called

        # Verify flow_status is updated to active
        update_calls = mock_store.update_flow_state.call_args_list
        last_update = update_calls[-1]
        _, kwargs = last_update
        assert kwargs.get("flow_status") == "active"

        # Verify event was recorded
        assert mock_store.add_event.called
        event_call = mock_store.add_event.call_args
        assert event_call[0][1] == "flow_reactivated"
