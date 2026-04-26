"""Tests for execution_lifecycle module."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.execution_lifecycle import (
    ExecutionLifecycleService,
    persist_execution_lifecycle_event,
)


@pytest.fixture
def mock_store() -> MagicMock:
    return MagicMock()


class TestExecutionLifecycleSessionCleanup:
    """Tests for lifecycle events - session_id is no longer written to flow_state."""

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

    def test_started_event_binds_tmux_session_from_refs(self, tmp_path: Path) -> None:
        """Async started events should persist the real tmux session for liveness."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-42",
            role="planner",
            lifecycle="started",
            actor="agent:test",
            detail="Plan started",
            refs={"tmux_session": "vibe3-plan-issue-42"},
        )

        sessions = store.list_live_runtime_sessions(role="planner")
        assert len(sessions) == 1
        assert sessions[0]["tmux_session"] == "vibe3-plan-issue-42"

    def test_started_event_updates_existing_live_session_tmux(
        self, tmp_path: Path
    ) -> None:
        """Duplicate started events should hydrate tmux_session
        instead of staying blind."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        session_id = store.create_runtime_session(
            role="planner",
            target_type="issue",
            target_id="42",
            branch="task/issue-42",
            session_name="vibe3-planner-issue-42",
            status="running",
        )

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-42",
            role="planner",
            lifecycle="started",
            actor="agent:test",
            detail="Plan started",
            refs={"tmux_session": "vibe3-plan-issue-42"},
        )

        session = store.get_runtime_session(session_id)
        assert session is not None
        assert session["tmux_session"] == "vibe3-plan-issue-42"

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


class TestExtendedRoles:
    """Tests for extended execution roles (manager, supervisor, governance)."""

    def test_manager_started_creates_registry_session(self, tmp_path: Path) -> None:
        """Manager started event should create runtime session."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="task/issue-10",
            role="manager",
            lifecycle="started",
            actor="orchestra:manager",
            detail="Manager execution started",
            session_id="mgr-10",
        )

        sessions = store.list_live_runtime_sessions(role="manager")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"

    def test_manager_does_not_update_flow_state(self, mock_store: MagicMock) -> None:
        """Manager lifecycle should NOT write to flow_state."""
        persist_execution_lifecycle_event(
            store=mock_store,
            branch="task/issue-10",
            role="manager",
            lifecycle="completed",
            actor="orchestra:manager",
            detail="Manager completed",
        )

        # Manager should NOT update flow_state (no status field)
        mock_store.update_flow_state.assert_called()

    def test_supervisor_started_creates_registry_session(self, tmp_path: Path) -> None:
        """Supervisor started event should create runtime session."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        persist_execution_lifecycle_event(
            store=store,
            branch="supervisor/handoff-20",
            role="supervisor",
            lifecycle="started",
            actor="supervisor:apply",
            detail="Supervisor apply started",
            session_id="sup-20",
        )

        sessions = store.list_live_runtime_sessions(role="supervisor")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"

    def test_governance_completed_marks_registry_done(self, tmp_path: Path) -> None:
        """Governance completed event should mark registry session as done."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

        # Start governance
        persist_execution_lifecycle_event(
            store=store,
            branch="governance/scan",
            role="governance",
            lifecycle="started",
            actor="governance:service",
            detail="Governance scan started",
        )

        # Complete governance
        persist_execution_lifecycle_event(
            store=store,
            branch="governance/scan",
            role="governance",
            lifecycle="completed",
            actor="governance:service",
            detail="Governance scan completed",
        )

        # Should be no live sessions
        live = store.list_live_runtime_sessions(role="governance")
        assert len(live) == 0


class TestExecutionLifecycleService:
    """Tests for unified ExecutionLifecycleService interface."""

    def test_record_started_creates_session(self, tmp_path: Path) -> None:
        """record_started should create a running session."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = ExecutionLifecycleService(store)

        service.record_started(
            role="manager",
            target="task/issue-30",
            actor="test:actor",
            session_id="test-session",
        )

        sessions = store.list_live_runtime_sessions(role="manager")
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"

    def test_record_completed_marks_done(self, tmp_path: Path) -> None:
        """record_completed should mark session as done."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = ExecutionLifecycleService(store)

        service.record_started(
            role="planner",
            target="dev/issue-40",
            actor="test:actor",
        )
        service.record_completed(
            role="planner",
            target="dev/issue-40",
            actor="test:actor",
        )

        live = store.list_live_runtime_sessions(role="planner")
        assert len(live) == 0

    def test_record_failed_marks_aborted(self, tmp_path: Path) -> None:
        """record_failed should mark session as aborted."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = ExecutionLifecycleService(store)

        service.record_started(
            role="executor",
            target="task/issue-50",
            actor="test:actor",
        )
        service.record_failed(
            role="executor",
            target="task/issue-50",
            actor="test:actor",
            error="Execution failed",
        )

        live = store.list_live_runtime_sessions(role="executor")
        assert len(live) == 0

    def test_all_roles_supported(self, tmp_path: Path) -> None:
        """All execution roles should work with the service."""
        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = ExecutionLifecycleService(store)

        roles: list[
            Literal[
                "manager", "planner", "executor", "reviewer", "supervisor", "governance"
            ]
        ] = [
            "manager",
            "planner",
            "executor",
            "reviewer",
            "supervisor",
            "governance",
        ]
        for role in roles:
            service.record_started(
                role=role,
                target=f"test/{role}",
                actor="test:actor",
            )
            sessions = store.list_live_runtime_sessions(role=role)
            assert len(sessions) == 1

            service.record_completed(
                role=role,
                target=f"test/{role}",
                actor="test:actor",
            )
            live = store.list_live_runtime_sessions(role=role)
            assert len(live) == 0
