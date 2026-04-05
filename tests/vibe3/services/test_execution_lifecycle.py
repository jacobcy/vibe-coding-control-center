"""Tests for execution_lifecycle module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.services.execution_lifecycle import (
    persist_execution_lifecycle_event,
)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock()


class TestExecutionLifecycleSessionCleanup:
    """Tests for session id cleanup on terminal lifecycle events."""

    def test_completed_lifecycle_clears_session_id(self, mock_store: MagicMock) -> None:
        """Completed lifecycle should clear session id for re-entry."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="planner",
            lifecycle="completed",
            actor="agent:test",
            detail="Plan completed successfully",
            session_id="ses_plan_42",
        )

        # Verify session_id was cleared (set to None) on terminal state
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("planner_session_id") is None

    def test_aborted_lifecycle_clears_session_id(self, mock_store: MagicMock) -> None:
        """Aborted lifecycle should clear session id for re-entry."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="executor",
            lifecycle="aborted",
            actor="agent:test",
            detail="Execution aborted due to error",
            session_id="ses_exec_42",
        )

        # Verify session_id was cleared (set to None) on terminal state
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("executor_session_id") is None

    def test_started_lifecycle_keeps_session_id(self, mock_store: MagicMock) -> None:
        """Started lifecycle should keep session id (not terminal)."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="reviewer",
            lifecycle="started",
            actor="agent:test",
            detail="Review started",
            session_id="ses_review_42",
        )

        # Verify session_id was persisted
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("reviewer_session_id") == "ses_review_42"

        # Started is not terminal, session_id should be kept
        # (not cleared until completed/aborted)

    def test_completed_preserves_actor_and_event_history(
        self, mock_store: MagicMock
    ) -> None:
        """Completed lifecycle should preserve actor and event history."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="planner",
            lifecycle="completed",
            actor="agent:test",
            detail="Plan completed",
            session_id="ses_plan_42",
        )

        # Verify actor field was updated
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("planner_actor") == "agent:test"

        # Verify event was added to history
        mock_store.add_event.assert_called_once()
        event_call = mock_store.add_event.call_args
        assert event_call.args[0] == "task/issue-42"
        assert event_call.args[1] == "plan_completed"
        assert event_call.args[2] == "agent:test"

    def test_aborted_preserves_actor_and_event_history(
        self, mock_store: MagicMock
    ) -> None:
        """Aborted lifecycle should preserve actor and event history."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="executor",
            lifecycle="aborted",
            actor="agent:test",
            detail="Execution aborted",
            session_id="ses_exec_42",
        )

        # Verify actor field was updated
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("executor_actor") == "agent:test"

        # Verify event was added to history
        mock_store.add_event.assert_called_once()
        event_call = mock_store.add_event.call_args
        assert event_call.args[0] == "task/issue-42"
        assert event_call.args[1] == "run_aborted"
        assert event_call.args[2] == "agent:test"


class TestExecutionLifecycleReEntry:
    """Tests for re-entry after terminal lifecycle events."""

    def test_stale_planner_session_does_not_block_re_entry(
        self, mock_store: MagicMock
    ) -> None:
        """Stale planner session_id should not block legal re-plan."""
        # Simulate first plan completed
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="planner",
            lifecycle="completed",
            actor="agent:test1",
            detail="First plan completed",
            session_id="ses_plan_42_v1",
        )

        # TODO: After implementation, simulate re-plan scenario
        # This test documents that stale session_id should not block re-entry
        # Currently, the session_id persists and would block re-dispatch
        # After Task 4 implementation, re-entry should be allowed

    def test_stale_executor_session_does_not_block_re_entry(
        self, mock_store: MagicMock
    ) -> None:
        """Stale executor session_id should not block legal re-run."""
        # Simulate first run aborted
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="executor",
            lifecycle="aborted",
            actor="agent:test1",
            detail="First run aborted",
            session_id="ses_exec_42_v1",
        )

        # TODO: After implementation, simulate re-run scenario
        # This test documents that stale session_id should not block re-entry
        # Currently, the session_id persists and would block re-dispatch
        # After Task 4 implementation, re-entry should be allowed

    def test_stale_reviewer_session_does_not_block_re_entry(
        self, mock_store: MagicMock
    ) -> None:
        """Stale reviewer session_id should not block legal re-review."""
        # Simulate first review completed
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="reviewer",
            lifecycle="completed",
            actor="agent:test1",
            detail="First review completed",
            session_id="ses_review_42_v1",
        )

        # TODO: After implementation, simulate re-review scenario
        # This test documents that stale session_id should not block re-entry
        # Currently, the session_id persists and would block re-dispatch
        # After Task 4 implementation, re-entry should be allowed
