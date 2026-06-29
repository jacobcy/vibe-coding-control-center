"""State machine definitions for issue label transitions.

Moved from domain layer to models to break circular dependency:
services.label_service → domain.state_machine

These are pure data definitions and validation functions with no
dependencies on domain layer concepts.
"""

from __future__ import annotations

from vibe3.exceptions import InvalidTransitionError
from vibe3.models import ALLOWED_TRANSITIONS, FORBIDDEN_TRANSITIONS, IssueState

VIBE_TASK_LABEL = "vibe-task"

STATE_PRIORITY_ORDER: tuple[str, ...] = (
    "blocked",
    "done",
    "merge-ready",
    "review",
    "in-progress",
    "handoff",
    "claimed",
    "ready",
)


def get_highest_priority_state_label(labels: list[str]) -> str | None:
    """Return the highest-priority ``state/*`` label from *labels*, or ``None``.

    Priority order: blocked > done > merge-ready > review > in-progress >
    handoff > claimed > ready.
    """
    state_set = {lb for lb in labels if lb.startswith("state/")}
    for priority in STATE_PRIORITY_ORDER:
        candidate = f"state/{priority}"
        if candidate in state_set:
            return candidate
    return None

STATE_LABEL_META: dict[IssueState, tuple[str, str]] = {
    IssueState.READY: ("0E8A16", "Ready for manager dispatch"),
    IssueState.CLAIMED: ("1D76DB", "Claimed and waiting for planning"),
    IssueState.IN_PROGRESS: ("FBCA04", "Execution in progress"),
    IssueState.BLOCKED: ("D93F0B", "Blocked and waiting for follow-up"),
    IssueState.HANDOFF: ("5319E7", "Waiting for manager handoff decision"),
    IssueState.REVIEW: ("0052CC", "Waiting for review execution"),
    IssueState.MERGE_READY: ("0E8A16", "Ready to merge"),
    IssueState.DONE: ("6A737D", "Flow completed"),
}


def can_transition(from_state: IssueState, to_state: IssueState) -> bool:
    """Return whether a transition is allowed by domain rules."""
    if (from_state, to_state) in FORBIDDEN_TRANSITIONS:
        return False
    return (from_state, to_state) in ALLOWED_TRANSITIONS


def validate_transition(
    from_state: IssueState | None,
    to_state: IssueState,
    *,
    force: bool = False,
) -> None:
    """Validate a state transition against domain rules."""
    if force or from_state is None:
        return
    if (from_state, to_state) in FORBIDDEN_TRANSITIONS:
        raise InvalidTransitionError(from_state.value, to_state.value)
    if (from_state, to_state) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(from_state.value, to_state.value)
