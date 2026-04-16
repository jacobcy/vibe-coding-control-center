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


# ============================================================================
# State Machine Diagram
# ============================================================================
#
# Decision makers: [M]anager AI agent  [C]ode layer (auto)  [H]uman (resume)
#
#   READY ───────────────────────────────────────────────────────────────
#     │
#     │ [M] handle_ready: claim or block
#     ▼
#   CLAIMED ─────────────────────────────────────────────────────────────
#     │  │
#     │  │ [C] planner fails → FAILED
#     │  │ [C] no plan_ref   → BLOCKED (no-op gate)
#     │  │ [M] plan_ref exists, AI advances → HANDOFF
#     │  │
#     ▼  ▼
#   HANDOFF ◄───────────────────────────────────────────────────────────
#     │  ▲       ▲
#     │  │       │  [C] executor/reviewer completes, no auto-transition
#     │  │       │  [M] reads refs, decides next action
#     │  │       │
#     │  ├───────┘  [M] handle_handoff: dispatch next role
#     │  │
#     │  │ [M] plan_ref exists → IN_PROGRESS
#     │  │ [M] report_ref exists → REVIEW
#     │  │ [M] audit_ref + verdict=PASS → MERGE_READY
#     │  │ [M] cannot proceed → BLOCKED
#     ▼  ▼
#   IN_PROGRESS          REVIEW            MERGE_READY
#     │  ▲                 │  ▲               │
#     │  │ [C] no report   │  │ [C] no audit  │ [M] write MERGE_READY_COMMIT
#     │  │  → BLOCKED      │  │  → BLOCKED    │     → IN_PROGRESS (commit mode)
#     │  │                 │  │               │
#     │  └─────────────────┘  └──── HANDOFF   │
#     │                         ▲             │
#     │                         │ pr_ref      │
#     │                         │             ▼
#     └──── HANDOFF ◄──── IN_PROGRESS (commit: PR created)
#              │
#              │ [M] review pr_ref → DONE
#              ▼
#             DONE
#
#   BLOCKED ◄──── any state (via [C] no-op gate or [M] business decision)
#     │
#     │ [H] vibe3 task resume --blocked / --label (force=True)
#     └──→ READY or HANDOFF (human decides)
#
#   FAILED ◄──── CLAIMED / IN_PROGRESS / REVIEW (via [C] execution error)
#     │
#     │ [C] auto-retry paths (FAILED → CLAIMED/HANDOFF/IN_PROGRESS/REVIEW)
#     │ [H] vibe3 task resume --failed (force=True → READY)
#     └──→ READY (human decides)
#
# Key invariants (Issue #303):
#   1. Code layer NEVER auto-transitions to HANDOFF (no-op gate)
#   2. BLOCKED has NO automatic exit (requires human resume with force=True)
#   3. State decisions belong to: manager AI (normal) or human (override)
# ============================================================================

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
    (IssueState.MERGE_READY, IssueState.IN_PROGRESS),  # executor commits + PR
    (IssueState.HANDOFF, IssueState.DONE),  # manager concludes after PR review
    # Side paths (→ blocked)
    (IssueState.READY, IssueState.BLOCKED),
    (IssueState.CLAIMED, IssueState.BLOCKED),
    (IssueState.HANDOFF, IssueState.BLOCKED),
    (IssueState.IN_PROGRESS, IssueState.BLOCKED),
    (IssueState.REVIEW, IssueState.BLOCKED),
    (IssueState.MERGE_READY, IssueState.BLOCKED),
    # NOTE: blocked → other states removed (修复 Issue #303)
    # blocked 状态不允许自动转换，必须等人类核查
    # 手动 resume 命令可以用 force=True 绕过
    # Execution failures
    (IssueState.CLAIMED, IssueState.FAILED),
    (IssueState.IN_PROGRESS, IssueState.FAILED),
    (IssueState.REVIEW, IssueState.FAILED),
    (IssueState.FAILED, IssueState.CLAIMED),
    (IssueState.FAILED, IssueState.HANDOFF),
    (IssueState.FAILED, IssueState.IN_PROGRESS),
    (IssueState.FAILED, IssueState.REVIEW),
}

# Progress expectations for each state
# (the artifact that must be created to consider it "progressed")
# Format: State -> Field in handoff/refs
STATE_PROGRESS_CONTRACT: dict[IssueState, str | None] = {
    IssueState.READY: None,  # System enforces MUST transition (claimed/blocked only)
    IssueState.HANDOFF: None,  # System enforces MUST transition
    IssueState.CLAIMED: "plan_ref",
    IssueState.IN_PROGRESS: "report_ref",  # also accepts pr_ref (commit mode)
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
    (IssueState.READY, IssueState.DONE),
    (IssueState.CLAIMED, IssueState.DONE),
    (IssueState.BLOCKED, IssueState.DONE),
    (IssueState.FAILED, IssueState.DONE),
    (IssueState.MERGE_READY, IssueState.DONE),
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
    milestone: str | None = None  # GitHub milestone title

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

            # Parse GitHub milestone
            milestone = None
            milestone_data = payload.get("milestone")
            if isinstance(milestone_data, dict) and "title" in milestone_data:
                milestone = milestone_data["title"]

            return cls(
                number=int(payload["number"]),
                title=str(payload.get("title", "")),
                state=state,
                labels=labels,
                assignees=[a["login"] for a in payload.get("assignees", [])],
                url=payload.get("html_url") or payload.get("url"),
                milestone=milestone,
            )
        except (KeyError, ValueError) as exc:
            logger.bind(domain="orchestra").warning(
                f"Cannot parse issue payload: {exc}"
            )
            return None
