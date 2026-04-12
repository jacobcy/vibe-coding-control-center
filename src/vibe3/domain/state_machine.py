"""Domain state-machine rules and metadata for issue label transitions."""

from __future__ import annotations

from vibe3.exceptions import InvalidTransitionError
from vibe3.models.orchestration import (
    ALLOWED_TRANSITIONS,
    FORBIDDEN_TRANSITIONS,
    IssueState,
)

VIBE_TASK_LABEL = "vibe-task"

STATE_LABEL_META: dict[IssueState, tuple[str, str]] = {
    IssueState.READY: ("0E8A16", "Ready for manager dispatch"),
    IssueState.CLAIMED: ("1D76DB", "Claimed and waiting for planning"),
    IssueState.IN_PROGRESS: ("FBCA04", "Execution in progress"),
    IssueState.BLOCKED: ("D93F0B", "Blocked and waiting for follow-up"),
    IssueState.FAILED: ("B60205", "Execution failed and needs recovery"),
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
