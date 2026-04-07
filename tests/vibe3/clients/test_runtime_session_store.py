"""Tests for runtime session store (create/get/update/list)."""

import pytest

from vibe3.clients.sqlite_client import SQLiteClient


def test_runtime_session_roundtrip(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    session_id = store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="431",
        branch="task/issue-431",
        session_name="vibe3-manager-issue-431",
        status="starting",
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["role"] == "manager"
    assert session["status"] == "starting"


def test_create_runtime_session_returns_int(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    session_id = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="100",
        branch="task/issue-100",
        session_name="vibe3-executor-issue-100",
    )

    assert isinstance(session_id, int)
    assert session_id > 0


def test_get_runtime_session_not_found(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    result = store.get_runtime_session(99999)
    assert result is None


def test_update_runtime_session(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    session_id = store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="200",
        branch="task/issue-200",
        session_name="vibe3-planner-issue-200",
        status="starting",
    )

    store.update_runtime_session(
        session_id, status="running", backend_session_id="abc123"
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "running"
    assert session["backend_session_id"] == "abc123"


def test_list_live_runtime_sessions(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    id1 = store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="300",
        branch="task/issue-300",
        session_name="vibe3-manager-issue-300",
        status="starting",
    )
    id2 = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="301",
        branch="task/issue-301",
        session_name="vibe3-executor-issue-301",
        status="running",
    )
    id3 = store.create_runtime_session(
        role="reviewer",
        target_type="issue",
        target_id="302",
        branch="task/issue-302",
        session_name="vibe3-reviewer-issue-302",
        status="done",
    )

    live = store.list_live_runtime_sessions()
    live_ids = [s["id"] for s in live]
    assert id1 in live_ids
    assert id2 in live_ids
    assert id3 not in live_ids


def test_list_live_runtime_sessions_filter_by_role(
    tmp_path: pytest.TempPathFactory,
) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="400",
        branch="task/issue-400",
        session_name="vibe3-manager-issue-400",
        status="running",
    )
    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="401",
        branch="task/issue-401",
        session_name="vibe3-executor-issue-401",
        status="running",
    )

    manager_sessions = store.list_live_runtime_sessions(role="manager")
    assert len(manager_sessions) == 1
    assert manager_sessions[0]["role"] == "manager"


def test_runtime_session_all_fields(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    session_id = store.create_runtime_session(
        role="executor",
        target_type="pr",
        target_id="42",
        branch="task/issue-42",
        session_name="vibe3-executor-pr-42",
        status="running",
        backend_session_id="sess-xyz",
        tmux_session="vibe-42",
        log_path="/tmp/log.txt",
        worktree_path="/tmp/wt",
    )

    session = store.get_runtime_session(session_id)
    assert session is not None
    assert session["target_type"] == "pr"
    assert session["target_id"] == "42"
    assert session["backend_session_id"] == "sess-xyz"
    assert session["tmux_session"] == "vibe-42"
    assert session["log_path"] == "/tmp/log.txt"
    assert session["worktree_path"] == "/tmp/wt"
    assert session["created_at"] is not None
    assert session["updated_at"] is not None
