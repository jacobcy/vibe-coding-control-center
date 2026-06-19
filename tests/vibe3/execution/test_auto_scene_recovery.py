"""Tests for auto-scene recovery service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.auto_scene_recovery import AutoSceneRecoveryService
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models import ExecutionRequest


@pytest.fixture
def mock_dependencies():
    config = MagicMock()
    store = MagicMock()
    backend = MagicMock()
    capacity = MagicMock()
    return config, store, backend, capacity


def test_auto_scene_reset_recovers_damaged_auto_worktree(
    mock_dependencies,
    tmp_path: Path,
):
    """Detached registered auto scenes should be reset and re-queued."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    target_path = tmp_path / ".worktrees" / "task/issue-42"
    target_path.mkdir(parents=True)

    service = AutoSceneRecoveryService(store=store)

    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        cmd=["echo", "hello"],
        repo_path=str(tmp_path),
        worktree_requirement=WorktreeRequirement.PERMANENT,
        tick_id=7,
    )

    mock_registry = MagicMock()
    mock_registry.get_truly_live_sessions_for_branch.return_value = []

    def fake_resolve_repo_path(req: ExecutionRequest) -> Path:
        return Path(req.repo_path) if req.repo_path else tmp_path

    with (
        patch(
            "vibe3.environment.find_worktree_by_path",
            return_value=True,
        ),
        patch(
            "vibe3.environment.find_worktree_for_branch",
            return_value=None,
        ),
        patch(
            "vibe3.execution.auto_scene_recovery._read_worktree_head",
            return_value="HEAD",
        ),
        patch("vibe3.services.orchestra.record_error") as mock_record_error,
        patch("vibe3.services.flow.FlowRebuildUsecase") as rebuild_cls,
    ):
        rebuild = MagicMock()
        rebuild_cls.return_value = rebuild

        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result.launched is False
    assert result.skipped is True
    assert result.reason_code == "auto_scene_reset"
    mock_record_error.assert_called_once()
    rebuild.rebuild_issue_flow.assert_called_once()
    call = rebuild.rebuild_issue_flow.call_args.kwargs
    assert call["issue"].number == 42
    assert call["issue"].title == "Issue 42"
    assert call["branch"] == "task/issue-42"
    assert call["reason"].startswith("Damaged auto scene detected")
    assert call["include_remote"] is True
    assert call["ensure_worktree"] is True
    assert store.add_event.call_count == 2


def test_auto_scene_reset_does_not_directly_unblock_without_rebuild(
    mock_dependencies,
    tmp_path: Path,
):
    """Damaged auto scenes must be hard rebuilt, not merely unblocked."""
    _config, store, _backend, _capacity = mock_dependencies
    (tmp_path / ".worktrees" / "task/issue-42").mkdir(parents=True)
    service = AutoSceneRecoveryService(store=store)
    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        cmd=["echo", "hello"],
        repo_path=str(tmp_path),
        worktree_requirement=WorktreeRequirement.PERMANENT,
    )

    mock_registry = MagicMock()
    mock_registry.get_truly_live_sessions_for_branch.return_value = []

    def fake_resolve_repo_path(req: ExecutionRequest) -> Path:
        return Path(req.repo_path) if req.repo_path else tmp_path

    with (
        patch(
            "vibe3.environment.find_worktree_by_path",
            return_value=True,
        ),
        patch(
            "vibe3.environment.find_worktree_for_branch",
            return_value=None,
        ),
        patch(
            "vibe3.execution.auto_scene_recovery._read_worktree_head",
            return_value="HEAD",
        ),
        patch("vibe3.services.orchestra.record_error"),
        patch("vibe3.services.flow.FlowRebuildUsecase"),
        patch("vibe3.services.BlockedStateService") as blocked_cls,
    ):
        service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    blocked_cls.assert_not_called()


def test_auto_scene_reset_skips_when_live_session_exists(
    mock_dependencies,
    tmp_path: Path,
):
    """Live auto scenes must not be force-reset by the recovery path."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    target_path = tmp_path / ".worktrees" / "task/issue-42"
    target_path.mkdir(parents=True)

    service = AutoSceneRecoveryService(store=store)

    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        cmd=["echo", "hello"],
        repo_path=str(tmp_path),
        worktree_requirement=WorktreeRequirement.PERMANENT,
    )

    mock_registry = MagicMock()
    mock_registry.get_truly_live_sessions_for_branch.return_value = [
        {"id": 1, "branch": "task/issue-42", "tmux_session": "live"}
    ]

    def fake_resolve_repo_path(req: ExecutionRequest) -> Path:
        return Path(req.repo_path) if req.repo_path else tmp_path

    with (
        patch("vibe3.services.orchestra.record_error") as mock_record_error,
        patch("vibe3.services.flow.FlowRebuildUsecase") as mock_cleanup_cls,
    ):
        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result is None
    mock_record_error.assert_not_called()
    mock_cleanup_cls.assert_not_called()


def test_auto_scene_reset_reports_rebuild_failure(
    mock_dependencies,
    tmp_path: Path,
):
    """Auto-reset should report failure if flow rebuild fails."""
    config, store, backend, capacity = mock_dependencies
    capacity.can_dispatch.return_value = True

    target_path = tmp_path / ".worktrees" / "task/issue-42"
    target_path.mkdir(parents=True)

    service = AutoSceneRecoveryService(store=store)

    request = ExecutionRequest(
        role="manager",
        target_branch="task/issue-42",
        target_id=42,
        execution_name="vibe3-manager-issue-42",
        cmd=["echo", "hello"],
        repo_path=str(tmp_path),
        worktree_requirement=WorktreeRequirement.PERMANENT,
        tick_id=7,
    )

    mock_registry = MagicMock()
    mock_registry.get_truly_live_sessions_for_branch.return_value = []

    def fake_resolve_repo_path(req: ExecutionRequest) -> Path:
        return Path(req.repo_path) if req.repo_path else tmp_path

    with (
        patch(
            "vibe3.environment.find_worktree_by_path",
            return_value=True,
        ),
        patch(
            "vibe3.environment.find_worktree_for_branch",
            return_value=None,
        ),
        patch(
            "vibe3.execution.auto_scene_recovery._read_worktree_head",
            return_value="HEAD",
        ),
        patch("vibe3.services.orchestra.record_error") as mock_record_error,
        patch("vibe3.services.flow.FlowRebuildUsecase") as rebuild_cls,
    ):
        rebuild = MagicMock()
        rebuild.rebuild_issue_flow.side_effect = RuntimeError("cleanup failed")
        rebuild_cls.return_value = rebuild

        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result.launched is False
    assert result.reason_code == "auto_scene_reset_failed"
    mock_record_error.assert_called_once()
    rebuild.rebuild_issue_flow.assert_called_once()
    assert store.add_event.call_count == 2
