"""Orchestration models for GitHub label state machine and issue data."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class IssueState(str, Enum):
    """GitHub issue orchestration state.

    Maps to GitHub label: state/{value}
    """

    READY = "ready"
    CLAIMED = "claimed"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    FAILED = "failed"
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
    (IssueState.CLAIMED, IssueState.HANDOFF),
    (IssueState.HANDOFF, IssueState.IN_PROGRESS),
    (IssueState.IN_PROGRESS, IssueState.HANDOFF),
    (IssueState.HANDOFF, IssueState.REVIEW),
    (IssueState.REVIEW, IssueState.HANDOFF),
    (IssueState.HANDOFF, IssueState.MERGE_READY),
    (IssueState.MERGE_READY, IssueState.DONE),
    # Side paths
    (IssueState.READY, IssueState.BLOCKED),
    (IssueState.CLAIMED, IssueState.BLOCKED),
    (IssueState.HANDOFF, IssueState.BLOCKED),
    (IssueState.IN_PROGRESS, IssueState.BLOCKED),
    (IssueState.REVIEW, IssueState.BLOCKED),
    (IssueState.MERGE_READY, IssueState.BLOCKED),
    (IssueState.BLOCKED, IssueState.CLAIMED),
    (IssueState.BLOCKED, IssueState.HANDOFF),
    # Execution failures
    (IssueState.CLAIMED, IssueState.FAILED),
    (IssueState.IN_PROGRESS, IssueState.FAILED),
    (IssueState.REVIEW, IssueState.FAILED),
    (IssueState.FAILED, IssueState.CLAIMED),
    (IssueState.FAILED, IssueState.HANDOFF),
    (IssueState.FAILED, IssueState.IN_PROGRESS),
    (IssueState.FAILED, IssueState.REVIEW),
    # Closure paths
    (IssueState.READY, IssueState.DONE),
    (IssueState.HANDOFF, IssueState.DONE),
    (IssueState.MERGE_READY, IssueState.DONE),
}

# Progress expectations for each state
# (the artifact that must be created to consider it "progressed")
# Format: State -> Field in handoff/refs
STATE_PROGRESS_CONTRACT: dict[IssueState, str | None] = {
    IssueState.READY: None,  # System enforces MUST transition (claimed/blocked/done)
    IssueState.HANDOFF: None,  # System enforces MUST transition
    IssueState.CLAIMED: "plan_ref",
    IssueState.IN_PROGRESS: "report_ref",
    IssueState.REVIEW: "audit_ref",
}

# Fallback targets for each state if progress contract is NOT met
STATE_FALLBACK_MATRIX: dict[IssueState, IssueState] = {
    IssueState.READY: IssueState.BLOCKED,
    IssueState.HANDOFF: IssueState.BLOCKED,
    IssueState.CLAIMED: IssueState.HANDOFF,
    IssueState.IN_PROGRESS: IssueState.HANDOFF,
    IssueState.REVIEW: IssueState.HANDOFF,
}

# Forbidden transitions (require force=True)
FORBIDDEN_TRANSITIONS: set[tuple[IssueState, IssueState]] = {
    (IssueState.CLAIMED, IssueState.DONE),
    (IssueState.BLOCKED, IssueState.DONE),
    (IssueState.FAILED, IssueState.DONE),
}


# ---------------------------------------------------------------------------
# Issue data model (used by the orchestra subsystem)
# ---------------------------------------------------------------------------


class IssueInfo(BaseModel):
    """GitHub issue information used during orchestration dispatch."""

    number: int
    title: str
    state: IssueState | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)  # GitHub login names
    url: str | None = None

    @property
    def slug(self) -> str:
        """Generate a URL-safe slug from the issue title."""
        slug = self.title.lower()
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")[:50]

    @classmethod
    def from_github_payload(cls, payload: dict[str, Any]) -> IssueInfo | None:
        """Create IssueInfo from a raw GitHub webhook issue payload.

        Handles both webhook format (nested ``labels`` objects) and
        list-issues format (flat dicts with ``assignees`` arrays).
        Returns None if the payload cannot be parsed.
        """
        try:
            labels = [lb["name"] for lb in payload.get("labels", [])]

            state = None
            for lb in labels:
                parsed = IssueState.from_label(lb)
                if parsed is not None:
                    state = parsed
                    break

            return cls(
                number=int(payload["number"]),
                title=str(payload.get("title", "")),
                state=state,
                labels=labels,
                assignees=[a["login"] for a in payload.get("assignees", [])],
                url=payload.get("html_url") or payload.get("url"),
            )
        except (KeyError, ValueError) as exc:
            logger.bind(domain="orchestra").warning(
                f"Cannot parse issue payload: {exc}"
            )
            return None
