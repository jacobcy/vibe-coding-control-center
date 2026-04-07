"""Tests for execution_lifecycle module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.execution_lifecycle import (
    persist_execution_lifecycle_event,
)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock()


class TestExecutionLifecycleSessionCleanup:
    """Tests for lifecycle events - session_id is no longer written to flow_state."""

    def test_completed_lifecycle_updates_status(self, mock_store: MagicMock) -> None:
        """Completed lifecycle should update status field."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="planner",
            lifecycle="completed",
            actor="agent:test",
            detail="Plan completed successfully",
            session_id="ses_plan_42",
        )

        # Verify status was updated
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("planner_status") == "done"
        # session_id is NOT written to flow_state (registry is source of truth)
        assert "planner_session_id" not in call_kwargs

    def test_aborted_lifecycle_updates_status(self, mock_store: MagicMock) -> None:
        """Aborted lifecycle should update status field."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="executor",
            lifecycle="aborted",
            actor="agent:test",
            detail="Execution aborted due to error",
            session_id="ses_exec_42",
        )

        # Verify status was updated
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("executor_status") == "crashed"
        # session_id is NOT written to flow_state (registry is source of truth)
        assert "executor_session_id" not in call_kwargs

    def test_started_lifecycle_updates_status(self, mock_store: MagicMock) -> None:
        """Started lifecycle should update status field."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-42",
            role="reviewer",
            lifecycle="started",
            actor="agent:test",
            detail="Review started",
            session_id="ses_review_42",
        )

        # Verify status was updated
        call_kwargs = mock_store.update_flow_state.call_args.kwargs
        assert call_kwargs.get("reviewer_status") == "running"
        # session_id is NOT written to flow_state (registry is source of truth)
        assert "reviewer_session_id" not in call_kwargs

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

        # Registry is now the source of truth for re-entry decisions
        # flow_state no longer contains session_id for dispatch gating

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

        # Registry is now the source of truth for re-entry decisions

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

        # Registry is now the source of truth for re-entry decisions


class TestRegistrySync:
    """Tests for runtime_session registry sync via lifecycle events."""

    def test_started_event_creates_running_registry_session(
        self, tmp_path: Path
    ) -> None:
        """started event should create a running record in runtime_session table."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="dev/issue-99",
            role="planner",
            lifecycle="started",
            actor="agent:test",
            detail="Plan started",
            session_id="test-session-abc",
        )

        sessions = store.list_live_runtime_sessions(role="planner")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"
        assert sessions[0]["branch"] == "dev/issue-99"

    def test_completed_event_marks_registry_session_done(self, tmp_path: Path) -> None:
        """completed event should update the live registry session to done."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-42",
            role="executor",
            lifecycle="started",
            actor="agent:test",
            detail="Run started",
            session_id="ses-exec-42",
        )
        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-42",
            role="executor",
            lifecycle="completed",
            actor="agent:test",
            detail="Run completed",
            session_id="ses-exec-42",
        )

        live = store.list_live_runtime_sessions(role="executor")
        assert len(live) == 0

    def test_aborted_event_marks_registry_session_aborted(self, tmp_path: Path) -> None:
        """aborted event should update the live registry session to aborted."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-55",
            role="reviewer",
            lifecycle="started",
            actor="agent:test",
            detail="Review started",
            session_id="ses-review-55",
        )
        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-55",
            role="reviewer",
            lifecycle="aborted",
            actor="agent:test",
            detail="Review aborted",
            session_id="ses-review-55",
        )

        # Aborted session should not appear in live list
        live = store.list_live_runtime_sessions(role="reviewer")
        assert len(live) == 0

    def test_target_id_extracted_from_branch(self, tmp_path: Path) -> None:
        """target_id should be the issue number extracted from the branch name."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-123",
            role="planner",
            lifecycle="started",
            actor="agent:test",
            detail="Plan started",
            session_id="ses-plan-123",
        )

        sessions = store.list_live_runtime_sessions(role="planner")
        assert len(sessions) == 1
        assert sessions[0]["target_id"] == "123"
        assert sessions[0]["target_type"] == "issue"
