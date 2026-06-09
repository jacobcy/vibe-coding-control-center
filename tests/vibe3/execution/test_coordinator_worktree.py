"""Tests for coordinator worktree/cwd resolution.

Covers _resolve_cwd behavior:
- cwd=None + NONE → returns None (no worktree)
- cwd=None + PERMANENT → resolves via WorktreeManager
- explicit cwd → short-circuits, ignoring worktree_requirement
- full dispatch integration with permanent worktree
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models import ExecutionRequest


@pytest.fixture
def mock_dependencies():
    config = MagicMock()
    store = MagicMock()
    backend = MagicMock()
    capacity = MagicMock()
    return config, store, backend, capacity


@patch("vibe3.execution.coordinator.WorktreeManager")
def test_coordinator_resolves_permanent_worktree_for_manager(
    mock_worktree_cls, mock_dependencies, tmp_path
):
    """Coordinator should own permanent worktree resolution for manager-like roles."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    handle = MagicMock()
    handle.tmux_session = "manager-session"
    handle.log_path = Path("/tmp/manager.log")

    mock_start_async = MagicMock(return_value=handle)
    coordinator = ExecutionCoordinator(
        config=config,
        store=store,
        backend=backend,
        capacity=capacity,
        start_async=mock_start_async,
    )

    mock_worktree = MagicMock()
    mock_worktree.resolve_manager_cwd.return_value = (tmp_path, False)
    mock_worktree_cls.return_value = mock_worktree

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


def test_resolve_cwd_returns_none_when_worktree_none(mock_dependencies):
    """cwd=None + worktree_requirement=NONE -> returns None (no worktree resolution)."""
    config, store, backend, capacity = mock_dependencies

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
        cwd=None,
        repo_path="/tmp/repo",
        worktree_requirement=WorktreeRequirement.NONE,
    )

    cwd_path = coordinator._resolve_cwd(request)
    assert cwd_path is None


@patch("vibe3.execution.coordinator.WorktreeManager")
def test_resolve_cwd_resolves_worktree_when_permanent_and_no_explicit_cwd(
    mock_worktree_cls, mock_dependencies, tmp_path
):
    """cwd=None + PERMANENT + repo_path: resolves via WorktreeManager."""
    config, store, backend, capacity = mock_dependencies

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
        role="planner",
        target_branch="dev/issue-99",
        target_id=99,
        execution_name="vibe3-planner-issue-99",
        cmd=["echo", "plan"],
        cwd=None,
        repo_path="/tmp/repo",
        worktree_requirement=WorktreeRequirement.PERMANENT,
    )

    cwd_path = coordinator._resolve_cwd(request)

    assert cwd_path == tmp_path
    mock_worktree_cls.assert_called_once_with(config, Path("/tmp/repo"))
    mock_worktree.resolve_manager_cwd.assert_called_once_with(99, "dev/issue-99")


@patch("vibe3.execution.coordinator.WorktreeManager")
def test_resolve_cwd_respects_explicit_cwd_over_worktree_requirement(
    mock_worktree_cls, mock_dependencies, tmp_path
):
    """Explicit cwd should short-circuit, ignoring worktree_requirement."""
    config, store, backend, capacity = mock_dependencies

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
        cwd="/explicit/path",
        worktree_requirement=WorktreeRequirement.PERMANENT,
    )

    cwd_path = coordinator._resolve_cwd(request)
    assert cwd_path == Path("/explicit/path")
    mock_worktree_cls.assert_not_called()
