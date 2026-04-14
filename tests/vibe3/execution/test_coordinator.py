"""Tests for execution coordinator."""

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
    lifecycle = MagicMock()
    return config, store, backend, capacity, lifecycle


def test_coordinator_dispatch_success(mock_dependencies):
    """Test successful async dispatch."""
    config, store, backend, capacity, lifecycle = mock_dependencies

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
            lifecycle=lifecycle,
        )

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

        # Verify capacity checked and in-flight managed
        capacity.can_dispatch.assert_called_once_with("planner", 42)
        capacity.mark_in_flight.assert_called_once_with("planner", 42)
        capacity.prune_in_flight.assert_called_once_with("planner", {42})

        # Verify start_async_command called correctly
        mock_start.assert_called_once_with(
            ["echo", "hello"],
            execution_name="vibe3-planner-issue-42",
            cwd=Path("/tmp/wt"),
            env={"FOO": "bar"},
        )

        # Verify lifecycle called with right refs
        expected_refs = {
            "extra": "value",
            "tmux_session": "test-session-123",
            "log_path": "/tmp/test.log",
        }
        lifecycle.record_started.assert_called_once_with(
            role="planner",
            target="task/issue-42",
            actor="orchestra:system",
            refs=expected_refs,
        )


def test_coordinator_dispatch_capacity_full(mock_dependencies):
    """Test dispatch rejected when capacity full."""
    config, store, backend, capacity, lifecycle = mock_dependencies

    # Setup capacity
    capacity.can_dispatch.return_value = False

    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
        lifecycle=lifecycle,
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

    # Verify backend and lifecycle not called
    backend.start_async_command.assert_not_called()
    lifecycle.record_started.assert_not_called()
    capacity.mark_in_flight.assert_not_called()


def test_coordinator_dispatch_launch_fails(mock_dependencies):
    """Test dispatch fails and records failure if launch throws."""
    config, store, backend, capacity, lifecycle = mock_dependencies

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
            lifecycle=lifecycle,
        )

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

        # Verify lifecycle record_failed was called
        lifecycle.record_started.assert_not_called()
        lifecycle.record_failed.assert_called_once_with(
            role="planner",
            target="task/issue-42",
            actor="orchestra:system",
            error="Tmux failed to start",
            refs={"issue_number": "42"},
        )

    # Verify capacity in-flight pruned even on error
    capacity.prune_in_flight.assert_called_once_with("planner", {42})


@patch("vibe3.execution.coordinator.WorktreeManager")
@patch("vibe3.execution.coordinator.start_async_command")
def test_coordinator_resolves_permanent_worktree_for_manager(
    mock_start_async, mock_worktree_cls, mock_dependencies, tmp_path
):
    """Coordinator should own permanent worktree resolution for manager-like roles."""
    config, store, backend, capacity, lifecycle = mock_dependencies
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
        lifecycle=lifecycle,
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
