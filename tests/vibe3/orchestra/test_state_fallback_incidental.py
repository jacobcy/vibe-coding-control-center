"""Regression tests for incidental close and closed issue semantics."""

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
async def test_handoff_closed_issue_does_not_create_new_close_semantics(
    orchestra_svc,
) -> None:
    """Handoff state should not gain close-as-progress semantics."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.HANDOFF
    svc.trigger_name = "manager"
    issue_num = 112
    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/handoff"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)  # Session ended

    # Issue was closed but state label unchanged (still handoff)
    before = {
        "state_label": "state/handoff",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
    }
    after = {
        "state_label": "state/handoff",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
        "issue_state": "closed",  # Issue closed but state label unchanged
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

            # Should STILL fallback because handoff does not get close-as-progress
            # semantics
            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.HANDOFF


@pytest.mark.asyncio
async def test_ready_incidental_close_without_abandon_still_blocks(
    orchestra_svc,
) -> None:
    """Ready state incidental close (no flow_status=aborted) triggers fallback."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 122
    # Issue is closed but still appears in list_issues with correct labels
    svc._github.list_issues.return_value = [_issue_payload(issue_num, ["state/ready"])]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)

    # Issue closed but flow NOT aborted (incidental close)
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
        "flow_status": "active",  # NOT aborted - incidental close
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

            # Should fallback because incidental close is NOT progress
            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.READY


@pytest.mark.asyncio
async def test_handoff_incidental_close_without_abandon_still_blocks(
    orchestra_svc,
) -> None:
    """Handoff state incidental close (no flow_status=aborted) triggers fallback."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.HANDOFF
    svc.trigger_name = "manager"
    issue_num = 123
    # Issue is closed but still appears in list_issues with correct labels
    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/handoff"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)

    # Issue closed but flow NOT aborted (incidental close)
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
        "flow_status": "active",  # NOT aborted - incidental close
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

            # Should fallback because incidental close is NOT progress
            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.HANDOFF
