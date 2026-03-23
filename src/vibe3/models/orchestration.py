"""Orchestration models for GitHub label state machine."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IssueState(str, Enum):
    """GitHub issue orchestration state.

    Maps to GitHub label: state/{value}
    """

    READY = "ready"
    CLAIMED = "claimed"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    HANDOFF = "handoff"
    REVIEW = "review"
    MERGE_READY = "merge-ready"
    DONE = "done"

    def to_label(self) -> str:
        """Convert to GitHub label name."""
        return f"state/{self.value}"

    @classmethod
    def from_label(cls, label: str) -> "IssueState | None":
        """Parse state from GitHub label."""
        if label.startswith("state/"):
            try:
                return cls(label[6:])
            except ValueError:
                pass
        return None


class StateTransition(BaseModel):
    """State transition record."""

    issue_number: int
    from_state: IssueState | None
    to_state: IssueState
    actor: str
    timestamp: datetime = Field(default_factory=datetime.now)
    forced: bool = False


# Allowed state transitions
ALLOWED_TRANSITIONS: set[tuple[IssueState, IssueState]] = {
    # Main chain
    (IssueState.READY, IssueState.CLAIMED),
    (IssueState.CLAIMED, IssueState.IN_PROGRESS),
    (IssueState.IN_PROGRESS, IssueState.REVIEW),
    (IssueState.REVIEW, IssueState.MERGE_READY),
    (IssueState.MERGE_READY, IssueState.DONE),
    # Side paths
    (IssueState.IN_PROGRESS, IssueState.BLOCKED),
    (IssueState.BLOCKED, IssueState.IN_PROGRESS),
    (IssueState.IN_PROGRESS, IssueState.HANDOFF),
    (IssueState.HANDOFF, IssueState.IN_PROGRESS),
    (IssueState.REVIEW, IssueState.IN_PROGRESS),
}

# Forbidden transitions (require force=True)
FORBIDDEN_TRANSITIONS: set[tuple[IssueState, IssueState]] = {
    (IssueState.READY, IssueState.DONE),
    (IssueState.CLAIMED, IssueState.DONE),
    (IssueState.BLOCKED, IssueState.DONE),
    (IssueState.HANDOFF, IssueState.DONE),
}
