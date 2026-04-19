"""Flow lifecycle domain events.

Events for agent execution lifecycle (planner, executor, reviewer).
"""

from dataclasses import dataclass

# Import base class from parent module
from vibe3.domain.events import DomainEvent as _DomainEvent

# Re-export for convenience
DomainEvent = _DomainEvent


@dataclass(frozen=True)
class IssueStateChanged(DomainEvent):
    """Issue state transition event.

    Published when an issue's state label changes.

    issue_title is optionally carried from polling (avoids redundant GitHub
    API calls in handlers that need to dispatch manager commands).
    """

    issue_number: int
    from_state: str | None
    to_state: str
    issue_title: str | None = None
    reason: str | None = None
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class IssueFailed(DomainEvent):
    """Issue failure event.

    Published when a role (executor/planner/reviewer/manager) fails.
    """

    issue_number: int
    reason: str
    actor: str = "system"
    role: str | None = None
    timestamp: str | None = None


# Dispatch-intent events (authoritative dispatch signals)


@dataclass(frozen=True)
class ManagerDispatched(DomainEvent):
    """Manager dispatch intent event.

    Authoritative signal that manager should be dispatched for an issue.
    Published by StateLabelDispatchService for ready/handoff manager triggers.
    """

    issue_number: int
    branch: str
    trigger_state: str  # "ready" | "handoff"
    issue_title: str | None = None
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None


@dataclass(frozen=True)
class PlannerDispatched(DomainEvent):
    """Planner dispatch intent event.

    Authoritative signal that planner should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="plan".
    """

    issue_number: int
    branch: str
    trigger_state: str  # "claimed"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None


@dataclass(frozen=True)
class ExecutorDispatched(DomainEvent):
    """Executor dispatch intent event.

    Authoritative signal that executor should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="run".

    Execution-specific context (plan_ref, audit_ref, commit_mode) is
    resolved by the handler layer, not carried on the dispatch intent.
    """

    issue_number: int
    branch: str
    trigger_state: str  # "in-progress"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None


@dataclass(frozen=True)
class ReviewerDispatched(DomainEvent):
    """Reviewer dispatch intent event.

    Authoritative signal that reviewer should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="review".

    Execution-specific context (report_ref) is resolved by the handler
    layer, not carried on the dispatch intent.
    """

    issue_number: int
    branch: str
    trigger_state: str  # "review"
    actor: str = "orchestra:dispatcher"
    timestamp: str | None = None
