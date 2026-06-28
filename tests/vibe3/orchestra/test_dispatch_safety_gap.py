"""Regression tests for the dispatch safety gap fix (issue #3220 C2).

Before C2, in-progress entries (``waiting_state`` set) short-circuited via an
early ``continue`` in ``_dispatch_loop``, bypassing ``should_skip_from_queue``,
the active-session-gate, and preflight. After C2 they flow through like any
other entry so remote intervention is detected and finished flows can be
re-dispatched to their next phase.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.domain.dispatch_preflight import DispatchPreflightDecision
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
    make_coordinator: object,
) -> None:
    """In-progress entry re-assigned to a non-manager must be popped."""
    coordinator: GlobalDispatchCoordinator = make_coordinator("manager")  # type: ignore[assignment]
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda n: _review_issue(["someone-else"])
    coordinator._emit_dispatch_intent = MagicMock()

    dispatched = coordinator._dispatch_loop(tick_id=1)

    assert dispatched == 0
    assert coordinator._frozen_queue == []
    coordinator._emit_dispatch_intent.assert_not_called()


def test_inprogress_entry_reaches_preflight_when_no_session(
    make_coordinator: object,
) -> None:
    """In-progress entry with no live session must reach preflight (not
    short-circuited by waiting_state). A failing preflight pops it."""
    coordinator: GlobalDispatchCoordinator = make_coordinator("manager")  # type: ignore[assignment]
    coordinator._frozen_queue = [_review_entry()]
    coordinator._load_issue = lambda n: _review_issue(["manager-bot"])
    coordinator._run_dispatch_preflight = lambda issue: DispatchPreflightDecision(
        allowed=False, target_state=None, reason="test-fail"
    )
    coordinator._emit_dispatch_intent = MagicMock()

    dispatched = coordinator._dispatch_loop(tick_id=1)

    assert dispatched == 0
    assert coordinator._frozen_queue == []
    coordinator._emit_dispatch_intent.assert_not_called()


def test_inprogress_entry_skipped_when_live_session(
    make_coordinator: object,
) -> None:
    """In-progress entry with an active live session is retained (skipped,
    not re-dispatched) via the active-session-gate."""
    coordinator: GlobalDispatchCoordinator = make_coordinator("manager")  # type: ignore[assignment]
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
