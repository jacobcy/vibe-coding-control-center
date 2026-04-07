"""Regression tests for progress semantics (close, abandon, noop blocking)."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


def _issue_payload(number: int, labels: list[str]) -> dict[str, object]:
    return {
        "number": number,
        "title": f"test issue {number}",
        "labels": [{"name": name} for name in labels],
        "assignees": [],
        "url": f"https://example.com/issues/{number}",
    }


@pytest.fixture
def orchestra_svc():
    manager = MagicMock()
    executor = ThreadPoolExecutor(max_workers=1)
    registry = MagicMock()
    registry.count_live_worker_sessions.return_value = 0
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True),
        trigger_state=IssueState.CLAIMED,
        trigger_name="plan",
        manager=manager,
        executor=executor,
        registry=registry,
    )
    svc._github = MagicMock()
    svc._store = MagicMock()
    svc._backend = MagicMock()
    svc._has_live_dispatch = MagicMock(return_value=False)
    try:
        yield svc, manager
    finally:
        executor.shutdown()


@pytest.mark.asyncio
async def test_ready_close_counts_as_progress_for_manager_sync(
    orchestra_svc,
) -> None:
    """Ready-manager path: issue close counts as valid progress."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 110
    # When issue is closed, list_issues(state="open") won't return it
    # So we mock with empty list to simulate closed issue not in open issues
    svc._github.list_issues.return_value = []
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)  # Session ended

    # Issue was open before, now closed (not in open issues list)
    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
    }
    after = {
        "state_label": "state/ready",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
        "issue_state": "closed",
    }
    # Set before snapshot
    svc._progress_snapshots[issue_num] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=after,
    ):
        with patch(
            "vibe3.orchestra.services.state_label_dispatch.execute_state_fallback"
        ) as mock_fallback:
            await svc.on_tick()

            # Should NOT fallback because closing counts as progress
            mock_fallback.assert_not_called()
            # Should be pruned from in-flight because issue is closed
            # (not in open issues list)
            assert issue_num not in svc._in_flight_dispatches


@pytest.mark.asyncio
async def test_ready_noop_still_blocks_when_issue_stays_open(
    orchestra_svc,
) -> None:
    """Ready state with no state change and issue still open should fall back
    to blocked."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 111
    svc._github.list_issues.return_value = [_issue_payload(issue_num, ["state/ready"])]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)  # Session ended

    # Issue stays open and state unchanged
    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
    }
    after = {
        "state_label": "state/ready",
        "comment_count": 1,  # Comment added but state unchanged
        "handoff": None,
        "refs": {},
        "issue_state": "open",  # Still open
    }
    svc._progress_snapshots[issue_num] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=after,
    ):
        with patch(
            "vibe3.orchestra.services.state_label_dispatch.execute_state_fallback"
        ) as mock_fallback:
            await svc.on_tick()

            # Should fallback because no state transition and issue not closed
            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.READY


@pytest.mark.asyncio
async def test_ready_abandon_counts_as_progress(orchestra_svc) -> None:
    """Ready state explicit abandon (flow_status=aborted) counts as progress."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 120
    svc._github.list_issues.return_value = []
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)

    # Issue closed and flow aborted
    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
        "flow_status": "active",
    }
    after = {
        "state_label": "state/ready",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
        "issue_state": "closed",
        "flow_status": "aborted",  # Explicit abandon
    }
    svc._progress_snapshots[issue_num] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=after,
    ):
        with patch(
            "vibe3.orchestra.services.state_label_dispatch.execute_state_fallback"
        ) as mock_fallback:
            await svc.on_tick()

            # Should NOT fallback because explicit abandon is progress
            mock_fallback.assert_not_called()
            assert issue_num not in svc._in_flight_dispatches


@pytest.mark.asyncio
async def test_handoff_abandon_counts_as_progress(orchestra_svc) -> None:
    """Handoff state explicit abandon (flow_status=aborted) counts as progress."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.HANDOFF
    svc.trigger_name = "manager"
    issue_num = 121
    svc._github.list_issues.return_value = []
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)

    # Issue closed and flow aborted
    before = {
        "state_label": "state/handoff",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
        "flow_status": "active",
    }
    after = {
        "state_label": "state/handoff",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
        "issue_state": "closed",
        "flow_status": "aborted",  # Explicit abandon
    }
    svc._progress_snapshots[issue_num] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=after,
    ):
        with patch(
            "vibe3.orchestra.services.state_label_dispatch.execute_state_fallback"
        ) as mock_fallback:
            await svc.on_tick()

            # Should NOT fallback because explicit abandon is progress
            mock_fallback.assert_not_called()
            assert issue_num not in svc._in_flight_dispatches
