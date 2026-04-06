"""Tests for StateLabelDispatchService no-progress parity logic."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

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
def manager_service() -> tuple[StateLabelDispatchService, MagicMock]:
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.READY,
        trigger_name="manager",
        manager=manager,
        executor=executor,
    )
    svc._github = MagicMock()
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._github.view_issue.return_value = {"number": 42, "comments": []}
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


# === Manager no-progress parity tests ===


@pytest.mark.asyncio
async def test_manager_async_path_blocks_on_comment_only_change_for_ready(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """READY state requires state transition; side effects like comments
    are NOT enough."""
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
    after = {
        "state_label": "state/ready",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
    }
    svc._progress_snapshots[42] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=after,
    ):
        await svc.on_tick()

    svc._github.add_comment.assert_called_once()
    comment = svc._github.add_comment.call_args[0][1]
    assert "Manager 执行完成但未改变状态" in comment


@pytest.mark.asyncio
async def test_manager_async_path_treats_handoff_changes_as_progress(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Async runtime path should treat handoff changes as progress."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    before_snapshot = {
        "state_label": "state/ready",
        "comment_count": 5,
        "handoff": "handoff_sig_before",
        "refs": {"plan_ref": "/tmp/plan.md"},
    }
    after_snapshot = {
        "state_label": "state/ready",
        "comment_count": 5,
        "handoff": "handoff_sig_after",
        "refs": {"plan_ref": "/tmp/plan.md"},
    }

    snapshot_calls = 0

    def mock_snapshot(*args, **kwargs):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return after_snapshot if snapshot_calls > 1 else before_snapshot

    import vibe3.orchestra.services.state_label_dispatch as dispatch_module

    original_snapshot = dispatch_module.snapshot_progress
    dispatch_module.snapshot_progress = mock_snapshot

    try:
        await svc.on_tick()

        manager.dispatch_manager.assert_called_once()
        assert 42 in svc._progress_snapshots

        manager.dispatch_manager.reset_mock()
        svc._in_flight_dispatches.add(42)

        await svc.on_tick()

        svc._github.add_comment.assert_called_once()
    finally:
        dispatch_module.snapshot_progress = original_snapshot


@pytest.mark.asyncio
async def test_manager_async_no_progress_block_fires_for_truly_no_change(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """No-progress block should fire when truly no observable change."""
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
