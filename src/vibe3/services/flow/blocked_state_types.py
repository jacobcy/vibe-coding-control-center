"""Data models for blocked state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vibe3.models import IssueState


@dataclass
class BlockedState:
    """Represents blocked state from a single source."""

    is_blocked: bool
    blocked_reason: str | None = None
    blocked_by: list[int] | None = None
    state: str | None = None  # "active", "blocked", "done", etc.

    @classmethod
    def not_blocked(cls) -> BlockedState:
        """Create a non-blocked state."""
        return cls(is_blocked=False)

    @classmethod
    def blocked(
        cls,
        reason: str,
        blocked_by: list[int] | None = None,
    ) -> BlockedState:
        """Create a blocked state."""
        return cls(
            is_blocked=True,
            blocked_reason=reason,
            blocked_by=blocked_by or [],
            state="blocked",
        )


@dataclass
class ConsistencyReport:
    """Report on three-source consistency."""

    database_state: BlockedState
    body_state: BlockedState
    label_state: BlockedState

    @property
    def is_consistent(self) -> bool:
        """True if all three sources agree on blocked status."""
        return (
            self.database_state.is_blocked == self.body_state.is_blocked
            and self.body_state.is_blocked == self.label_state.is_blocked
        )

    @property
    def authoritative_state(self) -> BlockedState:
        """Returns the truth-source state (issue body)."""
        return self.body_state


# ============================================================================
# Resume authority types (#3289: separate manual authorization from auto
# read-only eligibility — no permission-bearing boolean)
# ============================================================================


class ResumeSource(StrEnum):
    """Strong type distinguishing resume authority paths.

    MANUAL_COMMAND: human-invoked ``vibe3 task resume`` — authorized to clear
        blocked_reason and pick an explicit target state.
    SYSTEM_AUTO: observer path (check / orchestra / dispatch) — read-only
        eligibility, must NEVER clear a human blocked_reason.
    """

    MANUAL_COMMAND = "manual_command"
    SYSTEM_AUTO = "system_auto"


class AutoResumeVerdict(StrEnum):
    """Outcome of read-only auto resume eligibility evaluation."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


class AutoResumeReasonCode(StrEnum):
    """Stable reason code for auto resume (in)eligibility decisions.

    Used in low-noise observability events; values are part of the
    diagnostic contract and must not change casually.
    """

    ELIGIBLE = "eligible"
    HUMAN_REASON_PRESENT = "human_reason_present"
    DEPENDENCY_OPEN = "dependency_open"
    TRUTH_UNREADABLE = "truth_unreadable"


@dataclass(frozen=True)
class AutoResumeDecision:
    """Snapshot-bound auto resume eligibility decision.

    ``truth_snapshot`` carries the GitHub issue ``updatedAt`` timestamp read at
    evaluation time. ``apply_auto_resume`` re-reads ``updatedAt`` and rejects
    the decision as stale when it differs, preventing TOCTOU mutation races.

    Attributes:
        verdict: ELIGIBLE only when human reason is absent AND every
            dependency is confirmed CLOSED.
        reason_code: stable diagnostic code; ``eligible`` iff verdict is
            ELIGIBLE, otherwise one of ``human_reason_present``,
            ``dependency_open``, ``truth_unreadable``.
        issue_number: GitHub issue number.
        branch: Flow branch (may be empty for pre-flow issues).
        truth_snapshot: ``updatedAt`` captured at evaluate time, or None when
            GitHub omitted it.
        closed_deps: dependency issue numbers confirmed CLOSED — populated only
            when verdict == ELIGIBLE.
    """

    verdict: AutoResumeVerdict
    reason_code: AutoResumeReasonCode
    issue_number: int
    branch: str
    truth_snapshot: str | None
    closed_deps: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ResumeResult:
    """Outcome of a resume operation (manual or auto apply).

    Attributes:
        success: True when the blocked -> target transition was published.
        target_state: the state label actually written, or None when the
            operation refused or failed to advance.
        detail: human-readable diagnostic for logging and callers.
    """

    success: bool
    target_state: IssueState | None = None
    detail: str = ""
