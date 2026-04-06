"""Regression tests for state fallback closure and progress contract."""

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
    svc = StateLabelDispatchService(
        OrchestraConfig(dry_run=True),
        trigger_state=IssueState.CLAIMED,
        trigger_name="plan",
        manager=manager,
        executor=executor,
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
async def test_planner_no_progress_falls_back_to_handoff(orchestra_svc) -> None:
    svc, manager = orchestra_svc
    issue_num = 100
    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/claimed"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    # Simulate in-flight dispatch
    svc._in_flight_dispatches.add(issue_num)

    # Set up snapshots with NO change in plan_ref
    before = {
        "state_label": "state/claimed",
        "comment_count": 0,
        "handoff": None,
        "refs": {"plan_ref": None},
    }
    after = {
        "state_label": "state/claimed",
        "comment_count": 0,
        "handoff": None,
        "refs": {"plan_ref": None},
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

            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.CLAIMED


@pytest.mark.asyncio
async def test_planner_with_progress_does_not_fallback(orchestra_svc) -> None:
    svc, manager = orchestra_svc
    issue_num = 101
    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/claimed"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)

    # plan_ref changed!
    before = {
        "state_label": "state/claimed",
        "comment_count": 0,
        "handoff": None,
        "refs": {"plan_ref": None},
    }
    after = {
        "state_label": "state/claimed",
        "comment_count": 0,
        "handoff": None,
        "refs": {"plan_ref": "docs/plans/101.md"},
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

            mock_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_handoff_manager_eligible_without_plan_ref(orchestra_svc) -> None:
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.HANDOFF
    svc.trigger_name = "manager"
    issue_num = 102

    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/handoff"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    # No plan_ref, but should still be eligible for manager triage (Task 4 fix)
    svc._store.get_flow_state.return_value = {
        "plan_ref": None,
        "manager_session_id": None,
    }

    with patch.object(svc, "_dispatch_issue") as mock_dispatch:
        await svc.on_tick()
        mock_dispatch.assert_called_once()


@pytest.mark.asyncio
async def test_executor_no_progress_falls_back_to_handoff(orchestra_svc) -> None:
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.IN_PROGRESS
    svc.trigger_name = "run"
    issue_num = 103
    svc._github.list_issues.return_value = [
        _issue_payload(issue_num, ["state/in-progress"])
    ]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)

    # report_ref NOT changed
    before = {
        "state_label": "state/in-progress",
        "comment_count": 0,
        "handoff": None,
        "refs": {"report_ref": None},
    }
    after = {
        "state_label": "state/in-progress",
        "comment_count": 0,
        "handoff": None,
        "refs": {"report_ref": None},
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

            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.IN_PROGRESS


@pytest.mark.asyncio
async def test_ready_manager_no_progress_falls_back_to_blocked(
    orchestra_svc,
) -> None:
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 104
    svc._github.list_issues.return_value = [_issue_payload(issue_num, ["state/ready"])]
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)

    # NO change
    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
    }
    svc._progress_snapshots[issue_num] = before

    with patch(
        "vibe3.orchestra.services.state_label_dispatch.snapshot_progress",
        return_value=before,
    ):
        with patch(
            "vibe3.orchestra.services.state_label_dispatch.execute_state_fallback"
        ) as mock_fallback:
            await svc.on_tick()

            mock_fallback.assert_called_once()
            kwargs = mock_fallback.call_args[1]
            assert kwargs["source_state"] == IssueState.READY


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Close-as-progress logic needs further refinement in Task 5")
async def test_ready_close_counts_as_progress_for_manager_sync(
    orchestra_svc,
) -> None:
    """Ready-manager path: issue close counts as valid progress."""
    svc, manager = orchestra_svc
    svc.trigger_state = IssueState.READY
    svc.trigger_name = "manager"
    issue_num = 110
    svc._github.list_issues.return_value = [_issue_payload(issue_num, ["state/ready"])]
    svc._github.view_issue.return_value = {"number": issue_num, "comments": []}
    manager.flow_manager.get_flow_for_issue.return_value = {
        "branch": f"task/issue-{issue_num}"
    }

    svc._in_flight_dispatches.add(issue_num)
    svc._has_live_dispatch = MagicMock(return_value=False)  # Session ended

    # Issue was open before
    before = {
        "state_label": "state/ready",
        "comment_count": 0,
        "handoff": None,
        "refs": {},
        "issue_state": "open",
    }
    # Issue is now closed (state_label may still be state/ready, but issue is closed)
    after = {
        "state_label": "state/ready",
        "comment_count": 1,
        "handoff": None,
        "refs": {},
        "issue_state": "closed",
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

            # Should NOT fallback because closing counts as progress
            mock_fallback.assert_not_called()
            # Should be pruned from in-flight
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
