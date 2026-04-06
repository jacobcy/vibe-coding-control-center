"""Tests for StateLabelDispatchService."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.runtime.event_bus import GitHubEvent


def _issue_payload(
    number: int = 42, labels: list[str] | None = None
) -> dict[str, object]:
    issue_labels = labels or ["state/claimed"]
    return {
        "number": number,
        "title": "test issue",
        "labels": [{"name": name} for name in issue_labels],
        "assignees": [],
        "url": f"https://example.com/issues/{number}",
    }


def _event() -> GitHubEvent:
    return GitHubEvent(
        event_type="issues",
        action="labeled",
        payload={"issue": _issue_payload()},
        source="webhook",
    )


@pytest.fixture
def service() -> tuple[StateLabelDispatchService, MagicMock]:
    manager = MagicMock()
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.CLAIMED,
        trigger_name="plan",
        manager=manager,
        executor=executor,
    )
    svc._store = MagicMock()
    svc._store.get_flow_state.return_value = {"latest_actor": "agent:test"}
    svc._backend = MagicMock()
    svc._backend.start_async_command.return_value = MagicMock(
        tmux_session="vibe3-plan-issue-42",
        log_path=Path("/tmp/vibe3-plan-issue-42.log"),
    )
    svc._has_live_dispatch = MagicMock(return_value=False)
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


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
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


@pytest.fixture
def handoff_manager_service() -> tuple[StateLabelDispatchService, MagicMock]:
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True, max_concurrent_flows=2),
        trigger_state=IssueState.HANDOFF,
        trigger_name="manager",
        manager=manager,
        executor=executor,
    )
    svc._github = MagicMock()
    svc._store = MagicMock()
    try:
        yield svc, manager
    finally:
        executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_handle_event_is_noop(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = service

    await svc.handle_event(_event())

    manager.flow_manager.get_flow_for_issue.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_dispatches_matching_state(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]

    await svc.on_tick()

    svc._backend.start_async_command.assert_called_once()
    svc._store.update_flow_state.assert_called_once()
    assert "planner_session_id" not in svc._store.update_flow_state.call_args.kwargs


@pytest.mark.asyncio
async def test_on_tick_skips_when_plan_ref_already_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._store.get_flow_state.return_value = {"plan_ref": "/tmp/plan.md"}

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_skips_noncanonical_manual_flow_for_plan(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = service
    svc._github = MagicMock()
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "dev/issue-435"}

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_dispatches_manager_for_ready_issue(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()


@pytest.mark.asyncio
async def test_on_tick_skips_when_live_tmux_session_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    svc, _ = service
    svc._github = MagicMock()
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._has_live_dispatch.return_value = True

    await svc.on_tick()

    svc._backend.start_async_command.assert_not_called()


# === Manager no-progress blocking tests ===


@pytest.mark.asyncio
async def test_manager_no_progress_does_not_block_when_session_alive(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager session still alive -> do not block."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=True)
    # Simulate manager dispatch was in-flight
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    # Should not auto-block because session is alive
    svc._github.add_comment.assert_not_called()
    # Should not call dispatch again because already in-flight
    manager.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_manager_no_progress_blocks_when_session_ended(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager session ended and no observable progress -> block."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    # Simulate manager dispatch was in-flight but session ended
    svc._in_flight_dispatches.add(42)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    # Set up matching snapshots (no progress)
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

    # Should auto-block because session ended and state unchanged
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
    # Issue has both ready and blocked labels
    svc._github.list_issues.return_value = [
        _issue_payload(labels=["state/ready", "state/blocked"])
    ]
    svc._has_live_dispatch = MagicMock(return_value=False)
    # Simulate manager dispatch was in-flight but session ended
    svc._in_flight_dispatches.add(42)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    # Should not add duplicate comment because already blocked
    svc._github.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_manager_state_changed_does_not_auto_block(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager changed state label -> do not auto-block."""
    svc, manager = manager_service
    # Issue no longer has state/ready (manager changed it to state/claimed)
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    # Simulate manager dispatch was in-flight
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    # Should not auto-block because state changed (no longer ready)
    svc._github.add_comment.assert_not_called()
    # Should clean up from in-flight without blocking
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
        "manager_session_id": None,  # No live session
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    # Should dispatch manager for handoff resume
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
        "manager_session_id": "ses_manager42",  # Live session exists
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}
    # Simulate already in-flight
    svc._in_flight_dispatches.add(42)

    await svc.on_tick()

    # Should not dispatch again because live session exists
    manager.dispatch_manager.assert_not_called()
    # Should keep in-flight tracking
    assert 42 in svc._in_flight_dispatches


@pytest.mark.asyncio
async def test_manager_handoff_clears_stale_session_and_resumes(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue clears stale manager session and resumes."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._store.get_flow_state.return_value = {
        "plan_ref": "/tmp/plan.md",
        "manager_session_id": "ses_stale_manager42",
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()
    assert svc._store.update_flow_state.call_args.kwargs["manager_session_id"] is None


@pytest.mark.asyncio
async def test_manager_ready_clears_stale_session_and_redispatches(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/ready issue clears stale manager session and dispatches again."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._store.get_flow_state.return_value = {
        "manager_session_id": "ses_stale_manager42"
    }
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    manager.dispatch_manager.assert_called_once()
    assert svc._store.update_flow_state.call_args.kwargs["manager_session_id"] is None


@pytest.mark.asyncio
async def test_manager_handoff_skips_noncanonical_flow(
    handoff_manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """state/handoff issue does not resume manager for non-canonical flow."""
    svc, manager = handoff_manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/handoff"])]
    # Non-canonical branch (dev/ instead of task/)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "dev/issue-42"}

    await svc.on_tick()

    # Should not dispatch manager for non-canonical flow
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


# === Manager no-progress parity tests ===


@pytest.mark.asyncio
async def test_manager_async_path_treats_comment_changes_as_progress(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Async runtime path should treat comment count changes as progress."""
    svc, manager = manager_service
    # Issue still has state/ready but comment count changed
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    svc._in_flight_dispatches.add(42)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    # Comment count increased (manager made progress)
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

    # Should NOT auto-block because comment count changed (Task 3 fix)
    svc._github.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_manager_async_path_treats_handoff_changes_as_progress(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Async runtime path should treat handoff changes as progress."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    svc._has_live_dispatch = MagicMock(return_value=False)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    # Set up before snapshot with different handoff
    before_snapshot = {
        "state_label": "state/ready",
        "comment_count": 5,
        "handoff": "handoff_sig_before",
        "refs": {"plan_ref": "/tmp/plan.md"},
    }
    after_snapshot = {
        "state_label": "state/ready",  # State unchanged
        "comment_count": 5,
        "handoff": "handoff_sig_after",  # Handoff changed
        "refs": {"plan_ref": "/tmp/plan.md"},
    }

    # Mock snapshot_progress to simulate handoff change
    snapshot_calls = 0

    def mock_snapshot(*args, **kwargs):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return after_snapshot if snapshot_calls > 1 else before_snapshot

    # Patch snapshot_progress in the service
    import vibe3.orchestra.services.state_label_dispatch as dispatch_module

    original_snapshot = dispatch_module.snapshot_progress
    dispatch_module.snapshot_progress = mock_snapshot

    try:
        # First tick: dispatch manager and save before snapshot
        await svc.on_tick()

        # Should dispatch manager
        manager.dispatch_manager.assert_called_once()
        # Should have saved before snapshot
        assert 42 in svc._progress_snapshots

        # Reset mocks
        manager.dispatch_manager.reset_mock()
        # Add to in-flight to simulate dispatch happened
        svc._in_flight_dispatches.add(42)

        # Second tick: check for progress
        await svc.on_tick()

        # Should NOT auto-block because handoff changed (progress made)
        svc._github.add_comment.assert_not_called()
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

    # Identical snapshots
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

    # Should auto-block because session ended and no change at all
    svc._github.add_comment.assert_called_once()
    comment = svc._github.add_comment.call_args[0][1]
    assert "[dispatcher]" in comment
    assert "Manager 执行完成但未改变状态" in comment


# === Dispatch deduplication tests ===


@pytest.mark.asyncio
async def test_on_tick_does_not_dispatch_when_issue_already_in_flight(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Issue already in _in_flight_dispatches should not be dispatched again."""
    svc, manager = manager_service
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/ready"])]
    # Simulate issue already in-flight with live session
    svc._in_flight_dispatches.add(42)
    svc._has_live_dispatch = MagicMock(return_value=True)
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-42"}

    await svc.on_tick()

    # Should not dispatch again because already in-flight
    manager.dispatch_manager.assert_not_called()


@pytest.mark.asyncio
async def test_on_tick_does_not_dispatch_when_live_dispatch_exists(
    service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Issue with live dispatch should not be dispatched again."""
    svc, _ = service
    svc._github = MagicMock()
    svc._github.list_issues.return_value = [_issue_payload(labels=["state/claimed"])]
    # Simulate live dispatch exists
    svc._has_live_dispatch.return_value = True

    await svc.on_tick()

    # Should not dispatch because live session exists
    svc._backend.start_async_command.assert_not_called()


# === Manager capacity limit tests ===


@pytest.mark.asyncio
async def test_manager_tick_dispatches_at_most_remaining_capacity(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
) -> None:
    """Manager tick should respect remaining capacity and not over-dispatch."""
    svc, manager = manager_service
    # Set up 6 ready issues but max_concurrent_flows=2 (from fixture)
    # No active flows currently
    ready_issues = [
        _issue_payload(number=i, labels=["state/ready"])
        for i in [410, 417, 418, 419, 431, 436]
    ]
    svc._github.list_issues.return_value = ready_issues
    svc._has_live_dispatch = MagicMock(return_value=False)
    # No active flows and no in-flight dispatches
    manager.flow_manager.get_flow_for_issue.return_value = {"branch": "task/issue-410"}

    await svc.on_tick()

    # Should dispatch at most 2 (max_concurrent_flows) issues in this tick
    # Not all 6 ready issues
    assert manager.dispatch_manager.call_count <= 2
    # Verify that we dispatched at least one (capacity not zero)
    assert manager.dispatch_manager.call_count >= 1


@pytest.mark.asyncio
async def test_manager_tick_logs_throttled_issue_numbers_when_capacity_exhausted(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Throttled issues should be logged with their issue numbers."""

    from loguru import logger

    # Set up loguru to propagate to standard logging for caplog
    handler_id = logger.add(
        caplog.handler,  # Use pytest's caplog handler
        format="{message}",
        level="INFO",
    )

    try:
        svc, manager = manager_service
        # Set up 6 ready issues but max_concurrent_flows=2
        ready_issues = [
            _issue_payload(number=i, labels=["state/ready"])
            for i in [410, 417, 418, 419, 431, 436]
        ]
        svc._github.list_issues.return_value = ready_issues
        svc._has_live_dispatch = MagicMock(return_value=False)
        manager.flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-410"
        }

        await svc.on_tick()

        # Should log throttled issues
        # At least some issues should be throttled (capacity < ready count)
        log_messages = [record.message for record in caplog.records]
        # Look for evidence of throttling in logs
        assert any(
            "throttle" in msg.lower() or "capacity" in msg.lower()
            for msg in log_messages
        ), f"Expected throttle log, got: {log_messages}"
    finally:
        logger.remove(handler_id)


# === Tick logging detail tests ===


@pytest.mark.asyncio
async def test_manager_tick_logs_selected_dispatched_and_throttled_issues(
    manager_service: tuple[StateLabelDispatchService, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Manager tick should log which issues were selected, dispatched, and throttled."""
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}", level="INFO")

    try:
        svc, manager = manager_service
        # Set up 6 ready issues but max_concurrent_flows=2
        ready_issues = [
            _issue_payload(number=i, labels=["state/ready"])
            for i in [410, 417, 418, 419, 431, 436]
        ]
        svc._github.list_issues.return_value = ready_issues
        svc._has_live_dispatch = MagicMock(return_value=False)
        manager.flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-410"
        }

        await svc.on_tick()

        log_messages = [record.message for record in caplog.records]
        # Should log selected issues
        assert any(
            "410" in msg and "417" in msg for msg in log_messages
        ), f"Expected selected issues log, got: {log_messages}"
        # Should log throttled issues
        assert any(
            "418" in msg or "419" in msg or "431" in msg or "436" in msg
            for msg in log_messages
        ), f"Expected throttled issues log, got: {log_messages}"
    finally:
        logger.remove(handler_id)
