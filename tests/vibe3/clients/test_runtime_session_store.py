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


def test_delete_flow_removes_flow_truth_and_runtime_sessions(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Hard delete flow should remove all flow data permanently."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-500"

    store.update_flow_state(branch, flow_slug="issue-500", flow_status="active")
    store.add_event(branch, "flow_created", "test-user", "created")
    store.add_issue_link(branch, 500, "task")
    session_id = store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="500",
        branch=branch,
        session_name="vibe3-manager-issue-500",
        status="running",
    )

    assert store.get_flow_state(branch) is not None
    assert store.get_events(branch)
    assert store.get_issue_links(branch)
    assert store.get_runtime_session(session_id) is not None

    # Hard delete to remove all data
    store.delete_flow(branch, force=True)

    assert store.get_flow_state(branch) is None
    assert store.get_events(branch) == []
    assert store.get_issue_links(branch) == []
    assert store.get_runtime_session(session_id) is None


def test_get_latest_session_with_backend_id_returns_most_recent(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Should return the most recent session with backend_session_id."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-600"
    role = "executor"

    # Create older session
    store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="600",
        branch=branch,
        session_name="vibe3-executor-issue-600-v1",
        status="done",
        backend_session_id="old-session-id",
    )

    # Create newer session
    id2 = store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="600",
        branch=branch,
        session_name="vibe3-executor-issue-600-v2",
        status="done",
        backend_session_id="new-session-id",
    )

    result = store.get_latest_session_with_backend_id(branch=branch, role=role)
    assert result is not None
    assert result["id"] == id2
    assert result["backend_session_id"] == "new-session-id"


def test_get_latest_session_with_backend_id_returns_none_when_no_match(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Should return None when no sessions with backend_session_id exist."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    # Create session without backend_session_id
    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="601",
        branch="task/issue-601",
        session_name="vibe3-executor-issue-601",
        status="done",
    )

    result = store.get_latest_session_with_backend_id(
        branch="task/issue-601", role="executor"
    )
    assert result is None


def test_get_latest_session_with_backend_id_ignores_empty_string(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Should ignore sessions with empty string backend_session_id."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-602"

    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="602",
        branch=branch,
        session_name="vibe3-executor-issue-602",
        status="done",
        backend_session_id="",
    )

    result = store.get_latest_session_with_backend_id(branch=branch, role="executor")
    assert result is None


def test_get_latest_session_with_backend_id_ignores_null(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Should ignore sessions with NULL backend_session_id."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-603"

    store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="603",
        branch=branch,
        session_name="vibe3-executor-issue-603",
        status="done",
    )

    result = store.get_latest_session_with_backend_id(branch=branch, role="executor")
    assert result is None


def test_get_latest_session_with_backend_id_filters_by_role(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """Should only return sessions matching the specified role."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-604"

    # Create session with different role
    store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="604",
        branch=branch,
        session_name="vibe3-manager-issue-604",
        status="done",
        backend_session_id="manager-session-id",
    )

    result = store.get_latest_session_with_backend_id(branch=branch, role="executor")
    assert result is None


def test_stop_all_live_sessions(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))

    # Create sessions in different states
    id1 = store.create_runtime_session(
        role="manager",
        target_type="issue",
        target_id="1",
        branch="b1",
        session_name="s1",
        status="starting",
    )
    id2 = store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="2",
        branch="b1",
        session_name="s2",
        status="running",
    )
    id3 = store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="3",
        branch="b1",
        session_name="s3",
        status="stopped",
    )

    count = store.stop_all_live_sessions()
    assert count == 2

    # Verify live sessions are now stopped
    assert store.get_runtime_session(id1)["status"] == "stopped"
    assert store.get_runtime_session(id2)["status"] == "stopped"
    # Already-stopped session unchanged
    assert store.get_runtime_session(id3)["status"] == "stopped"


def test_stop_all_live_sessions_no_sessions(tmp_path: pytest.TempPathFactory) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    assert store.stop_all_live_sessions() == 0
