"""Tests for auto-scene recovery service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.execution.auto_scene_recovery import AutoSceneRecoveryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestration import IssueState
from vibe3.services import LiveSessionsDetectedError


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
            "vibe3.environment.worktree_support.find_worktree_by_path",
            return_value=True,
        ),
        patch(
            "vibe3.environment.worktree_support.find_worktree_for_branch",
            return_value=None,
        ),
        patch(
            "vibe3.execution.auto_scene_recovery._read_worktree_head",
            return_value="HEAD",
        ),
        patch(
            "vibe3.services.error_tracking_service.ErrorTrackingService"
        ) as mock_tracking,
        patch(
            "vibe3.services.flow_cleanup_service.FlowCleanupService"
        ) as mock_cleanup_cls,
        patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_blocked_cls,
    ):
        mock_cleanup = MagicMock()
        mock_cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup
        mock_blocked = MagicMock()
        mock_blocked_cls.return_value = mock_blocked

        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result.launched is False
    assert result.skipped is True
    assert result.reason_code == "auto_scene_reset"
    mock_tracking.get_instance.return_value.record_error.assert_called_once()
    mock_cleanup.cleanup_flow_scene.assert_called_once_with(
        "task/issue-42",
        include_remote=True,
        terminate_sessions=True,
        keep_flow_record=False,
    )
    mock_blocked.unblock.assert_called_once_with(
        branch="task/issue-42",
        target_state=IssueState.READY,
        issue_number=42,
        actor="orchestra:auto-recover",
        detail="Auto scene reset completed - issue returned to READY",
    )
    assert store.add_event.call_count == 2


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
        patch(
            "vibe3.services.error_tracking_service.ErrorTrackingService"
        ) as mock_tracking,
        patch(
            "vibe3.services.flow_cleanup_service.FlowCleanupService"
        ) as mock_cleanup_cls,
    ):
        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result is None
    mock_tracking.get_instance.return_value.record_error.assert_not_called()
    mock_cleanup_cls.assert_not_called()


def test_auto_scene_reset_aborted_on_live_session_race(
    mock_dependencies,
    tmp_path: Path,
):
    """Auto-reset should abort cleanly if LiveSessionsDetectedError is raised."""
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
            "vibe3.environment.worktree_support.find_worktree_by_path",
            return_value=True,
        ),
        patch(
            "vibe3.environment.worktree_support.find_worktree_for_branch",
            return_value=None,
        ),
        patch(
            "vibe3.execution.auto_scene_recovery._read_worktree_head",
            return_value="HEAD",
        ),
        patch(
            "vibe3.services.error_tracking_service.ErrorTrackingService"
        ) as mock_tracking,
        patch(
            "vibe3.services.flow_cleanup_service.FlowCleanupService"
        ) as mock_cleanup_cls,
    ):
        mock_cleanup = MagicMock()
        mock_cleanup.cleanup_flow_scene.side_effect = LiveSessionsDetectedError(
            "Live session detected during cleanup"
        )
        mock_cleanup_cls.return_value = mock_cleanup

        result = service.maybe_reset_damaged_scene(
            request,
            "Failed to resolve permanent worktree for manager:42",
            resolve_repo_path=fake_resolve_repo_path,
            registry=mock_registry,
        )

    assert result is None
    mock_tracking.get_instance.return_value.record_error.assert_called_once()
    mock_cleanup.cleanup_flow_scene.assert_called_once()
    assert store.add_event.call_count == 2
    abort_event = store.add_event.call_args_list[1]
    assert abort_event.args[1] == "auto_scene_reset_aborted"
