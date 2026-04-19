"""Tests for execution coordinator."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.role_contracts import WorktreeRequirement


@pytest.fixture
def mock_dependencies():
    config = MagicMock()
    store = MagicMock()
    backend = MagicMock()
    capacity = MagicMock()
    return config, store, backend, capacity


def test_coordinator_dispatch_success(mock_dependencies):
    """Test successful async dispatch."""
    config, store, backend, capacity = mock_dependencies

    # Setup capacity
    capacity.can_dispatch.return_value = True

    # Mock the module function start_async_command
    handle = MagicMock()
    handle.tmux_session = "test-session-123"
    handle.log_path = Path("/tmp/test.log")

    with patch(
        "vibe3.execution.coordinator.start_async_command", return_value=handle
    ) as mock_start:
        coordinator = ExecutionCoordinator(
            config=config,
            store=store,
            backend=backend,
            capacity=capacity,
        )
        coordinator.registry.reserve = MagicMock(return_value=123)
        coordinator.registry.mark_started = MagicMock()

        request = ExecutionRequest(
            role="planner",
            target_branch="task/issue-42",
            target_id=42,
            execution_name="vibe3-planner-issue-42",
            cmd=["echo", "hello"],
            cwd="/tmp/wt",
            env={"FOO": "bar"},
            refs={"extra": "value"},
        )

        result = coordinator.dispatch_execution(request)

        assert result.launched is True
        assert result.tmux_session == "test-session-123"
        assert result.log_path == "/tmp/test.log"

        # Verify capacity checked (no target_id parameter)
        capacity.can_dispatch.assert_called_once_with("planner")

        # Verify start_async_command called correctly
        mock_start.assert_called_once_with(
            ["echo", "hello"],
            execution_name="vibe3-planner-issue-42",
            cwd=Path("/tmp/wt"),
            env={"FOO": "bar"},
        )

        coordinator.registry.reserve.assert_called_once_with(
            role="planner",
            target_type="issue",
            target_id="42",
            branch="task/issue-42",
        )
        coordinator.registry.mark_started.assert_called_once_with(
            123,
            tmux_session="test-session-123",
            log_path="/tmp/test.log",
        )
        store.add_event.assert_called_once_with(
            "task/issue-42",
            "tmux_plan_started",
            "orchestra:system",
            detail="Planner tmux wrapper started",
            refs={
                "extra": "value",
                "tmux_session": "test-session-123",
                "log_path": "/tmp/test.log",
            },
        )


def test_coordinator_dispatch_capacity_full(mock_dependencies):
    """Test dispatch rejected when capacity full."""
    config, store, backend, capacity = mock_dependencies

    # Setup capacity
    capacity.can_dispatch.return_value = False

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )

    request = ExecutionRequest(
        role="planner",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-planner-issue-42",
        cmd=["echo", "hello"],
    )

    result = coordinator.dispatch_execution(request)

    assert result.launched is False
    assert "Capacity full" in result.reason
    assert result.reason_code == "capacity_full"


def test_sync_child_bypasses_parent_live_session_guard(mock_dependencies, monkeypatch):
    """Sync child process should not short-circuit on its async wrapper session."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )
    coordinator.registry.get_truly_live_sessions_for_target = MagicMock(
        return_value=[{"id": 1, "branch": "task/issue-42"}]
    )
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        prompt="do work",
        options=MagicMock(),
        mode="sync",
        refs={"task": "Manage issue #42"},
    )

    # Manager now routes through CodeagentExecutionService (unified shell)
    with patch("vibe3.execution.coordinator.CodeagentExecutionService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.stdout = "done"
        mock_svc.execute_sync_request.return_value = mock_result
        mock_svc_cls.return_value = mock_svc

        result = coordinator.dispatch_execution(request)

    assert result.launched is True
    coordinator.registry.get_truly_live_sessions_for_target.assert_not_called()
    mock_svc.execute_sync_request.assert_called_once()


def test_sync_child_clears_async_marker_before_entering_sync_shell(
    mock_dependencies, monkeypatch
):
    """Async child marker should stay on the outer wrapper, not leak into sync shell."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )
    monkeypatch.setenv("VIBE3_ASYNC_CHILD", "1")

    request = ExecutionRequest(
        role="planner",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-planner-issue-42",
        prompt="make a plan",
        options=MagicMock(),
        mode="sync",
        refs={"task": "plan issue #42"},
        actor="agent:planner",
    )

    seen_async_marker: list[str | None] = []

    with patch("vibe3.execution.coordinator.CodeagentExecutionService") as mock_svc_cls:
        mock_svc = MagicMock()

        def _capture_marker(*args, **kwargs):
            import os

            seen_async_marker.append(os.environ.get("VIBE3_ASYNC_CHILD"))
            return MagicMock(success=True, stdout="plan output", stderr="")

        mock_svc.execute_sync_request.side_effect = _capture_marker
        mock_svc_cls.return_value = mock_svc

        result = coordinator.dispatch_execution(request)

    assert result.launched is True
    assert seen_async_marker == [None]
    assert os.environ.get("VIBE3_ASYNC_CHILD") == "1"


def test_sync_non_child_still_blocks_duplicate_live_session(mock_dependencies):
    """Regular sync launches should still respect live-session dedupe."""
    config, store, backend, capacity = mock_dependencies

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )
    coordinator.registry.get_truly_live_sessions_for_target = MagicMock(
        return_value=[{"id": 1, "branch": "task/issue-42"}]
    )

    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        prompt="do work",
        options=MagicMock(),
        mode="sync",
    )

    result = coordinator.dispatch_execution(request)

    assert result.launched is False
    assert result.skipped is True
    assert result.reason_code == "already_running"
    backend.run.assert_not_called()


def test_sync_worker_uses_codeagent_execution_service(mock_dependencies):
    """Worker sync requests should route through the unified execution shell."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )

    request = ExecutionRequest(
        role="planner",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-planner-issue-42",
        prompt="make a plan",
        options=MagicMock(),
        mode="sync",
        refs={"task": "plan issue #42"},
        actor="agent:planner",
    )

    with patch(
        "vibe3.execution.coordinator.CodeagentExecutionService"
    ) as mock_service_cls:
        mock_result = MagicMock(
            success=True,
            stdout="plan output",
            stderr="",
        )
        mock_service = mock_service_cls.return_value
        mock_service.execute_sync_request.return_value = mock_result

        result = coordinator.dispatch_execution(request)

    assert result.launched is True
    assert result.stdout == "plan output"
    backend.run.assert_not_called()
    mock_service.execute_sync_request.assert_called_once_with(
        request,
        cwd=None,
    )


def test_sync_reviewer_uses_unified_execution_shell_for_pre_gate_callback(
    mock_dependencies,
):
    """Reviewer sync requests should rely on the unified shell for pre-gate work."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )

    request = ExecutionRequest(
        role="reviewer",
        target_branch="task/issue-55",
        target_id=55,
        execution_name="vibe3-reviewer-issue-55",
        prompt="review issue #55",
        options=MagicMock(),
        mode="sync",
        refs={"task": "review issue #55"},
        actor="agent:review",
    )

    with patch(
        "vibe3.execution.coordinator.CodeagentExecutionService"
    ) as mock_service_cls:
        mock_result = MagicMock(
            success=True,
            stdout="review output",
            stderr="",
        )
        mock_service = mock_service_cls.return_value
        mock_service.execute_sync_request.return_value = mock_result

        result = coordinator.dispatch_execution(request)

    assert result.launched is True
    assert result.stdout == "review output"
    backend.run.assert_not_called()
    mock_service.execute_sync_request.assert_called_once_with(
        request,
        cwd=None,
    )


def test_coordinator_dispatch_launch_fails(mock_dependencies):
    """Test dispatch fails and records failure if launch throws."""
    config, store, backend, capacity = mock_dependencies

    # Setup capacity
    capacity.can_dispatch.return_value = True

    # Mock the module function start_async_command to raise exception
    with patch("vibe3.execution.coordinator.start_async_command") as mock_start:
        mock_start.side_effect = Exception("Tmux failed to start")

        coordinator = ExecutionCoordinator(
            config=config,
            store=store,
            backend=backend,
            capacity=capacity,
        )
        coordinator.registry.reserve = MagicMock(return_value=123)
        coordinator.registry.mark_failed = MagicMock()

        request = ExecutionRequest(
            role="planner",
            target_branch="task/issue-42",
            target_id=42,
            execution_name="vibe3-planner-issue-42",
            cmd=["echo", "hello"],
            refs={"issue_number": "42"},
        )

        result = coordinator.dispatch_execution(request)

        assert result.launched is False
        assert "Tmux failed to start" in result.reason
        assert result.reason_code == "launch_failed"

        coordinator.registry.reserve.assert_called_once_with(
            role="planner",
            target_type="issue",
            target_id="42",
            branch="task/issue-42",
        )
        coordinator.registry.mark_failed.assert_called_once_with(123)


@patch("vibe3.execution.coordinator.WorktreeManager")
@patch("vibe3.execution.coordinator.start_async_command")
def test_coordinator_resolves_permanent_worktree_for_manager(
    mock_start_async, mock_worktree_cls, mock_dependencies, tmp_path
):
    """Coordinator should own permanent worktree resolution for manager-like roles."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    handle = MagicMock()
    handle.tmux_session = "manager-session"
    handle.log_path = Path("/tmp/manager.log")
    mock_start_async.return_value = handle

    mock_worktree = MagicMock()
    mock_worktree.resolve_manager_cwd.return_value = (tmp_path, False)
    mock_worktree_cls.return_value = mock_worktree

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
    )
    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-7",
        target_id=7,
        execution_name="vibe3-manager-issue-7",
        cmd=["echo", "manager"],
        repo_path="/tmp/repo",
        worktree_requirement=WorktreeRequirement.PERMANENT,
    )

    result = coordinator.dispatch_execution(request)

    assert result.launched is True
    mock_worktree_cls.assert_called_once_with(config, Path("/tmp/repo"))
    mock_worktree.resolve_manager_cwd.assert_called_once_with(7, "task/issue-7")
    mock_start_async.assert_called_once()
    call = mock_start_async.call_args
    assert call.args[0] == ["echo", "manager"]
    assert call.kwargs["execution_name"] == "vibe3-manager-issue-7"
    assert call.kwargs["cwd"] == tmp_path
