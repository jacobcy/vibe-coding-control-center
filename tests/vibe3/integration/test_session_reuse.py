"""Integration tests for session reuse across completed runs.

Tests verify the full session lifecycle:
1. Run 1: Create session → Run → Complete (write backend_session_id)
2. Run 2: load_session_id() returns completed backend_session_id
3. Backend receives correct session_id for resume
4. Safety net handles stale sessions correctly
"""

import subprocess
from unittest.mock import patch

from vibe3.agents.backends.session_manager import should_retry_without_session
from vibe3.clients import SQLiteClient
from vibe3.execution.session_service import load_session_id


def test_session_reuse_across_completed_runs(temp_store: SQLiteClient) -> None:
    """Verify session reuse works end-to-end when first run completes.

    Simulates the full lifecycle:
    - Run 1: Create session (status=running), backend returns session_id
    - Run 1: Complete → status changes to "done", backend_session_id written
    - Run 2: load_session_id() returns the backend_session_id from completed run
    """
    branch = "task/issue-2060"
    role = "executor"
    backend_session_id = "262f0fea-eacb-4223-b842-b5b5097f94e8"

    # Run 1: Create live session (status=running)
    session_id = temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2060",
        branch=branch,
        session_name="vibe3-executor-issue-2060",
        status="running",
    )
    assert session_id > 0

    # Verify no backend_session_id yet
    session = temp_store.get_runtime_session(session_id)
    assert session is not None
    assert session.get("backend_session_id") is None

    # Run 1: Complete → write backend_session_id, status="done"
    temp_store.update_runtime_session(
        session_id,
        backend_session_id=backend_session_id,
        status="done",
    )

    # Verify session is now completed with backend_session_id
    session = temp_store.get_runtime_session(session_id)
    assert session is not None
    assert session["status"] == "done"
    assert session["backend_session_id"] == backend_session_id

    # Run 2: load_session_id() should return the backend_session_id
    # Mock GitClient and SQLiteClient to use our test database
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store

        loaded_id = load_session_id(role)

    # Critical assertion: Session reuse works!
    assert loaded_id == backend_session_id


def test_session_reuse_ignores_null_backend_session_id(
    temp_store: SQLiteClient,
) -> None:
    """Verify sessions with NULL backend_session_id are ignored in fallback."""
    branch = "task/issue-2061"
    role = "executor"

    # Create completed session with NULL backend_session_id
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2061",
        branch=branch,
        session_name="vibe3-executor-issue-2061",
        status="done",
        # backend_session_id is NULL (not provided)
    )

    # Run 2: load_session_id() should return None
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store

        loaded_id = load_session_id(role)

    assert loaded_id is None


def test_session_reuse_ignores_invalid_session_id(temp_store: SQLiteClient) -> None:
    """Verify tmux session names are rejected by validation."""
    branch = "task/issue-2062"
    role = "executor"

    # Create completed session with tmux session name (invalid)
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2062",
        branch=branch,
        session_name="vibe3-executor-issue-2062",
        status="done",
        backend_session_id="vibe3-executor-issue-2062",  # Invalid: starts with "vibe3-"
    )

    # Run 2: load_session_id() should return None (validation rejects it)
    with patch("vibe3.execution.session_service.GitClient") as mock_git:
        mock_git.return_value.get_current_branch.return_value = branch

        loaded_id = load_session_id(role)

    assert loaded_id is None


def test_session_reuse_prefers_live_session_over_completed(
    temp_store: SQLiteClient,
) -> None:
    """Verify live sessions are preferred over completed sessions."""
    branch = "task/issue-2063"
    role = "executor"
    live_session_id = "live-session-id"
    completed_session_id = "completed-session-id"

    # Create live session with backend_session_id
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2063",
        branch=branch,
        session_name="vibe3-executor-issue-2063-live",
        status="running",
        backend_session_id=live_session_id,
    )

    # Create completed session with different backend_session_id
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2063",
        branch=branch,
        session_name="vibe3-executor-issue-2063-completed",
        status="done",
        backend_session_id=completed_session_id,
    )

    # Run 2: load_session_id() should prefer live session
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store

        loaded_id = load_session_id(role)

    # Should return live session ID, not completed
    assert loaded_id == live_session_id


def test_session_reuse_branch_isolation(temp_store: SQLiteClient) -> None:
    """Verify sessions don't leak across branches."""
    branch1 = "task/issue-2064"
    branch2 = "task/issue-2065"
    role = "executor"
    session1_id = "session-branch1"
    session2_id = "session-branch2"

    # Create session on branch1
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2064",
        branch=branch1,
        session_name="vibe3-executor-issue-2064",
        status="done",
        backend_session_id=session1_id,
    )

    # Create session on branch2
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2065",
        branch=branch2,
        session_name="vibe3-executor-issue-2065",
        status="done",
        backend_session_id=session2_id,
    )

    # Load session for branch1
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch1
        mock_store_cls.return_value = temp_store
        loaded_id = load_session_id(role)
    assert loaded_id == session1_id

    # Load session for branch2
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch2
        mock_store_cls.return_value = temp_store
        loaded_id = load_session_id(role)
    assert loaded_id == session2_id


def test_session_reuse_role_isolation(temp_store: SQLiteClient) -> None:
    """Verify sessions don't leak across roles."""
    branch = "task/issue-2066"
    executor_session_id = "executor-session"
    planner_session_id = "planner-session"

    # Create executor session
    temp_store.create_runtime_session(
        role="executor",
        target_type="issue",
        target_id="2066",
        branch=branch,
        session_name="vibe3-executor-issue-2066",
        status="done",
        backend_session_id=executor_session_id,
    )

    # Create planner session
    temp_store.create_runtime_session(
        role="planner",
        target_type="issue",
        target_id="2066",
        branch=branch,
        session_name="vibe3-planner-issue-2066",
        status="done",
        backend_session_id=planner_session_id,
    )

    # Load executor session
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store
        loaded_id = load_session_id("executor")
    assert loaded_id == executor_session_id

    # Load planner session
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store
        loaded_id = load_session_id("planner")
    assert loaded_id == planner_session_id


def test_safety_net_detects_stale_session(temp_store: SQLiteClient) -> None:
    """Verify should_retry_without_session catches stale backend sessions.

    This tests the safety net mechanism that handles stale sessions:
    - Backend session exists but has been deleted/invalidated
    - Wrapper returns exit code 42 with "session not found" error
    - should_retry_without_session() returns True
    - System retries without session_id
    """
    branch = "task/issue-2067"
    role = "executor"
    stale_session_id = "stale-session-id"

    # Create completed session with stale backend_session_id
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2067",
        branch=branch,
        session_name="vibe3-executor-issue-2067",
        status="done",
        backend_session_id=stale_session_id,
    )

    # Simulate backend failure: session not found
    result = subprocess.CompletedProcess(
        args=[],
        returncode=42,
        stdout="",
        stderr="Error: session not found: stale-session-id",
    )

    # Safety net should detect this
    assert should_retry_without_session(result, session_id=stale_session_id) is True

    # If exit code is different, should not retry
    result_ok = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="Success",
        stderr="",
    )
    assert should_retry_without_session(result_ok, session_id=stale_session_id) is False


def test_session_reuse_with_race_condition(temp_store: SQLiteClient) -> None:
    """Verify fallback works when live session has no backend_session_id yet.

    Race condition scenario:
    - Session starts (status="starting")
    - Backend returns session_id but session status still "starting"
    - Another run starts before first run completes
    """
    branch = "task/issue-2068"
    role = "executor"
    completed_session_id = "completed-session-id"

    # Create live session without backend_session_id (starting)
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2068",
        branch=branch,
        session_name="vibe3-executor-issue-2068-starting",
        status="starting",
        # backend_session_id is NULL
    )

    # Create completed session with backend_session_id
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2068",
        branch=branch,
        session_name="vibe3-executor-issue-2068-completed",
        status="done",
        backend_session_id=completed_session_id,
    )

    # Run 2: load_session_id() should fallback to completed session
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store

        loaded_id = load_session_id(role)

    # Should return completed session ID (fallback)
    assert loaded_id == completed_session_id


def test_session_reuse_returns_most_recent(temp_store: SQLiteClient) -> None:
    """Verify fallback returns most recent session when multiple exist."""
    branch = "task/issue-2069"
    role = "executor"
    old_session_id = "old-session-id"
    new_session_id = "new-session-id"

    # Create older completed session
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2069",
        branch=branch,
        session_name="vibe3-executor-issue-2069-v1",
        status="done",
        backend_session_id=old_session_id,
    )

    # Create newer completed session
    temp_store.create_runtime_session(
        role=role,
        target_type="issue",
        target_id="2069",
        branch=branch,
        session_name="vibe3-executor-issue-2069-v2",
        status="done",
        backend_session_id=new_session_id,
    )

    # Run 2: load_session_id() should return newest
    with (
        patch("vibe3.execution.session_service.GitClient") as mock_git,
        patch("vibe3.execution.session_service.SQLiteClient") as mock_store_cls,
    ):
        mock_git.return_value.get_current_branch.return_value = branch
        mock_store_cls.return_value = temp_store

        loaded_id = load_session_id(role)

    # Should return newer session ID
    assert loaded_id == new_session_id
