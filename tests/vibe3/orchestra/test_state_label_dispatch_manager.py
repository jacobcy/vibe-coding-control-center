"""Tests for StateLabelDispatchService manager state and blocking."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Generator
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


def _issue_payload(
    number: int = 42, labels: list[str] | None = None
) -> dict[str, object]:
    issue_labels = labels or ["state/ready"]
    return {
        "number": number,
        "title": "test issue",
        "labels": [{"name": name} for name in issue_labels],
        "assignees": [],
        "url": f"https://example.com/issues/{number}",
    }


@pytest.fixture
def manager_service() -> (
    Generator[tuple[StateLabelDispatchService, MagicMock], None, None]
):
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    registry = MagicMock()
    registry.count_live_worker_sessions.return_value = 0
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.READY,
        trigger_name="manager",
        manager=manager,
        executor=executor,
        registry=registry,
    )
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


@pytest.fixture
def handoff_manager_service() -> (
    Generator[tuple[StateLabelDispatchService, MagicMock], None, None]
):
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    registry = MagicMock()
    registry.count_live_worker_sessions.return_value = 0
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.HANDOFF,
        trigger_name="manager",
        manager=manager,
        executor=executor,
        registry=registry,
    )
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


# === Manager no-progress blocking tests ===


@pytest.mark.asyncio
async def test_manager_no_progress_does_not_block_when_session_alive(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager session still alive -> do not block."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=True)
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    svc._github.add_comment.assert_not_called()
    manager.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_manager_no_progress_blocks_when_session_ended(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager session ended and no observable progress -> block."""
    from unittest.mock import patch

    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._in_flight_dispatches.add(42)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
    }
    svc._progress_snapshots[42] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=before,
    ):
        await svc.on_tick()

    svc._github.add_comment.assert_called_once()
    comment = svc._github.add_comment.call_args[0][1]
    assert "[dispatcher]" in comment
    assert "Manager 执行完成但未改变状态" in comment


@pytest.mark.asyncio
async def test_manager_no_progress_skips_already_blocked_issue(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Already blocked issue -> do not duplicate block comment."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [
        _issue_payload(labels=["state/ready", "state/blocked"])
    ]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._in_flight_dispatches.add(42)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    svc._github.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_manager_state_changed_does_not_auto_block(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager changed state label -> do not auto-block."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    svc._github.add_comment.assert_not_called()
    assert 42 not in svc._in_flight_dispatches


# === Manager handoff resume tests ===


@pytest.mark.asyncio
async def test_manager_handoff_resume_with_valid_refs(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue with valid refs resumes manager automatically."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    svc._store.get_flow_state.return_value = {
        "plan_ref": "/tmp/plan.md",
        "handoff_ref": "/tmp/handoff.md",
        "manager_session_id": None,
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()
    call_issue = manager.dispatch_manager.call_args[0][0]
    assert call_issue.number == 42


@pytest.mark.asyncio
async def test_manager_handoff_does_not_double_dispatch_live_session(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue does not double-dispatch if live manager session exists."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    svc._has_live_dispatch = MagicMock(return_value=True)
    svc._store.get_flow_state.return_value = {
        "plan_ref": "/tmp/plan.md",
        "manager_session_id": "ses_manager42",
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    manager.dispatch_manager.assert_not_called()
    assert 42 in svc._in_flight_dispatches


@pytest.mark.asyncio
async def test_manager_handoff_dispatches_when_no_live_session(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue dispatches when registry shows no live session."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._store.get_flow_state.return_value = {
        "plan_ref": "/tmp/plan.md",
        "manager_session_id": "ses_stale_manager42",  # legacy field, ignored
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_manager_ready_dispatches_when_no_live_session(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/ready issue dispatches when registry shows no live session."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._store.get_flow_state.return_value = {
        "manager_session_id": "ses_stale_manager42"  # legacy field, ignored
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_manager_handoff_skips_noncanonical_flow(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue does not resume manager for non-canonical flow."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "dev/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_manager_handoff_blocked_issue_is_not_redispatched(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue already blocked should not be redispatched."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [
        _issue_payload(labels=["state/handoff", "state/blocked"])
    ]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._store.get_flow_state.return_value = {
        "plan_ref": "/tmp/plan.md",
        "manager_session_id": None,
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_not_called()
