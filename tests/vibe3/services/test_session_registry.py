"""Tests for SessionRegistryService."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.session_registry import SessionRegistryService


@pytest.fixture()
def store(tmp_path: pytest.TempPathFactory) -> SQLiteClient:
    return SQLiteClient(db_path=str(tmp_path / "handoff.db"))


@pytest.fixture()
def backend() -> MagicMock:
    mock = MagicMock()
    mock.has_tmux_session.return_value = True
    mock.has_tmux_session_prefix.return_value = True
    return mock


def test_reserve_returns_int(store: SQLiteClient, backend: MagicMock) -> None:
    registry = SessionRegistryService(store=store, backend=backend)
    session_id = registry.reserve(
        role="executor",
        target_type="issue",
        target_id="100",
        branch="task/issue-100",
    )
    assert isinstance(session_id, int)
    assert session_id > 0


def test_reserve_stores_session_with_starting_status(
    store: SQLiteClient, backend: MagicMock
) -> None:
    registry = SessionRegistryService(store=store, backend=backend)
    session_id = registry.reserve(
        role="executor",
        target_type="issue",
        target_id="200",
        branch="task/issue-200",
    )
    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "starting"
    assert session["role"] == "executor"
    assert session["session_name"] == "vibe3-executor-issue-200"


def test_mark_started_updates_status_to_running(
    store: SQLiteClient, backend: MagicMock
) -> None:
    registry = SessionRegistryService(store=store, backend=backend)
    session_id = registry.reserve(
        role="planner",
        target_type="issue",
        target_id="300",
        branch="task/issue-300",
    )
    registry.mark_started(session_id, tmux_session="vibe3-planner-issue-300")

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "running"
    assert session["tmux_session"] == "vibe3-planner-issue-300"


def test_mark_finished_success(store: SQLiteClient, backend: MagicMock) -> None:
    registry = SessionRegistryService(store=store, backend=backend)
    session_id = registry.reserve(
        role="reviewer",
        target_type="issue",
        target_id="400",
        branch="task/issue-400",
    )
    registry.mark_finished(session_id, success=True)

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "done"


def test_mark_finished_failure(store: SQLiteClient, backend: MagicMock) -> None:
    registry = SessionRegistryService(store=store, backend=backend)
    session_id = registry.reserve(
        role="executor",
        target_type="issue",
        target_id="500",
        branch="task/issue-500",
    )
    registry.mark_finished(session_id, success=False)

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "failed"


def test_count_live_worker_sessions_ignores_done_and_dead_tmux(
    store: SQLiteClient, backend: MagicMock
) -> None:
    registry = SessionRegistryService(store=store, backend=backend)

    # Create a running session with a live tmux session
    id_live = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="600",
        branch="task/issue-600",
        session_name="vibe3-executor-issue-600",
        status="running",
        tmux_session="live-a",
    )

    # Create a done session (should be ignored)
    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="601",
        branch="task/issue-601",
        session_name="vibe3-executor-issue-601",
        status="done",
        tmux_session="dead-b",
    )

    # Only "live-a" returns True from has_tmux_session
    backend.has_tmux_session.side_effect = lambda name: name == "live-a"

    count = registry.count_live_worker_sessions()
    assert count == 1
    _ = id_live  # used above


def test_count_live_worker_sessions_starting_with_no_tmux_counts_as_live(
    store: SQLiteClient, backend: MagicMock
) -> None:
    """Sessions in 'starting' status without a tmux_session are counted as live."""
    registry = SessionRegistryService(store=store, backend=backend)

    store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="700",
        branch="task/issue-700",
        session_name="vibe3-planner-issue-700",
        status="starting",
        # No tmux_session yet
    )

    backend.has_tmux_session.return_value = False

    count = registry.count_live_worker_sessions()
    assert count == 1


def test_count_live_worker_sessions_excludes_governance(
    store: SQLiteClient, backend: MagicMock
) -> None:
    """Governance sessions should not be counted in live worker sessions."""
    registry = SessionRegistryService(store=store, backend=backend)

    # Worker session
    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="800",
        branch="task/issue-800",
        session_name="vibe3-executor-issue-800",
        status="running",
        tmux_session="vibe3-executor-800",
    )

    # Governance session
    store.create_runtime_session(
        role="governance",
        target_type="governance",
        target_id="orchestra",
        branch="main",
        session_name="vibe3-governance-orchestra",
        status="running",
        tmux_session="vibe3-governance-orchestra",
    )

    backend.has_tmux_session.return_value = True

    count = registry.count_live_worker_sessions()
    assert count == 1


def test_count_live_worker_sessions_with_role_filter(
    store: SQLiteClient, backend: MagicMock
) -> None:
    registry = SessionRegistryService(store=store, backend=backend)

    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="900",
        branch="task/issue-900",
        session_name="vibe3-executor-issue-900",
        status="running",
        tmux_session="vibe3-executor-900",
    )
    store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="901",
        branch="task/issue-901",
        session_name="vibe3-planner-issue-901",
        status="running",
        tmux_session="vibe3-planner-901",
    )

    backend.has_tmux_session.return_value = True

    count = registry.count_live_worker_sessions(role="executor")
    assert count == 1


def test_reconcile_live_state_marks_orphaned(
    store: SQLiteClient, backend: MagicMock
) -> None:
    """Sessions where tmux is gone should be marked orphaned."""
    registry = SessionRegistryService(store=store, backend=backend)

    # Session with tmux that no longer exists
    orphan_id = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="1000",
        branch="task/issue-1000",
        session_name="vibe3-executor-issue-1000",
        status="running",
        tmux_session="dead-tmux",
    )

    # Session with live tmux
    alive_id = store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="1001",
        branch="task/issue-1001",
        session_name="vibe3-planner-issue-1001",
        status="running",
        tmux_session="alive-tmux",
    )

    backend.has_tmux_session.side_effect = lambda name: name == "alive-tmux"

    orphaned = registry.reconcile_live_state()
    assert orphan_id in orphaned
    assert alive_id not in orphaned

    orphan_session = store.get_runtime_session(orphan_id)
    assert orphan_session is not None
    assert orphan_session["status"] == "orphaned"

    alive_session = store.get_runtime_session(alive_id)
    assert alive_session is not None
    assert alive_session["status"] == "running"


def test_reconcile_live_state_ignores_starting_without_tmux(
    store: SQLiteClient, backend: MagicMock
) -> None:
    """Starting sessions without tmux_session should not be marked orphaned."""
    registry = SessionRegistryService(store=store, backend=backend)

    starting_id = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="1100",
        branch="task/issue-1100",
        session_name="vibe3-executor-issue-1100",
        status="starting",
    )

    backend.has_tmux_session.return_value = False

    orphaned = registry.reconcile_live_state()
    assert starting_id not in orphaned

    session = store.get_runtime_session(starting_id)
    assert session is not None
    assert session["status"] == "starting"
