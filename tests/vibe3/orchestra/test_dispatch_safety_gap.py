"""Regression tests for observation without in-flight redispatch."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.queue_entry import QueueEntry


def _review_entry(issue_number: int = 42) -> QueueEntry:
    """Build an in-progress (waiting) queue entry in REVIEW state."""
    return QueueEntry(
        issue_number=issue_number,
        collected_state="review",
        waiting_state="review",
    )


def _review_issue(assignees: list[str]) -> IssueInfo:
    """Build a REVIEW-state issue with the given assignees."""
    return IssueInfo(
        number=42,
        title="t",
        state=IssueState.REVIEW,
        labels=["state/review"],
        assignees=assignees,
    )


def test_inprogress_entry_kicked_on_non_manager_assignee(
    make_coordinator: Callable[..., GlobalDispatchCoordinator],
) -> None:
    """In-progress entry re-assigned to a non-manager must be popped."""
    coordinator = make_coordinator("manager")
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda n: _review_issue(["someone-else"])
    coordinator._emit_dispatch_intent = MagicMock()

    dispatched = coordinator._dispatch_loop(tick_id=1)

    assert dispatched == 0
    assert coordinator._frozen_queue == []
    coordinator._emit_dispatch_intent.assert_not_called()


def test_inprogress_entry_waits_for_state_change_when_no_session(
    make_coordinator: Callable[..., GlobalDispatchCoordinator],
) -> None:
    """An unchanged in-flight entry stays retained without redispatch."""
    coordinator = make_coordinator("manager")
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda n: _review_issue(["manager-bot"])
    coordinator._run_dispatch_preflight = MagicMock()
    coordinator._emit_dispatch_intent = MagicMock()

    dispatched = coordinator._dispatch_loop(tick_id=1)

    assert dispatched == 0
    assert coordinator._frozen_queue == [_review_entry()]
    coordinator._run_dispatch_preflight.assert_not_called()
    coordinator._emit_dispatch_intent.assert_not_called()


def test_inprogress_entry_skipped_when_live_session(
    make_coordinator: Callable[..., GlobalDispatchCoordinator],
) -> None:
    """In-progress entry with an active live session is retained (skipped,
    not re-dispatched) via the active-session-gate."""
    coordinator = make_coordinator("manager")
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda n: _review_issue(["manager-bot"])
    registry = MagicMock()
    registry.get_live_sessions_for_issue = MagicMock(
        return_value=[{"role": "reviewer"}]
    )
    coordinator._registry = registry
    coordinator._emit_dispatch_intent = MagicMock()

    dispatched = coordinator._dispatch_loop(tick_id=1)

    assert dispatched == 0
    assert len(coordinator._frozen_queue) == 1
    coordinator._emit_dispatch_intent.assert_not_called()
