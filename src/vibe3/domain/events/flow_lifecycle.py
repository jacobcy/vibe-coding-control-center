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

    Published when an executor/supervisor fails.
    """

    issue_number: int
    reason: str
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class IssueBlocked(DomainEvent):
    """Issue blocked event.

    Published when an issue is blocked due to missing requirements.
    """

    issue_number: int
    reason: str
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class ReportRefRequired(DomainEvent):
    """Report reference requirement event.

    Published when an authoritative report_ref is required.
    """

    issue_number: int
    branch: str
    ref_name: str
    reason: str
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class FlowBlocked(DomainEvent):
    """Flow blocked event.

    Published when a flow is blocked.
    """

    branch: str
    reason: str | None = None
    blocked_by_issue: int | None = None
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class FlowAborted(DomainEvent):
    """Flow aborted event.

    Published when a flow is aborted.
    """

    branch: str
    reason: str
    actor: str = "system"
    timestamp: str | None = None


@dataclass(frozen=True)
class PlanCompleted(DomainEvent):
    """Plan phase completed event.

    Published when planner completes successfully.
    """

    issue_number: int
    branch: str
    actor: str = "agent:plan"
    timestamp: str | None = None


@dataclass(frozen=True)
class ExecutionCompleted(DomainEvent):
    """Execution phase completed event.

    Published when executor completes successfully.
    """

    issue_number: int
    branch: str
    actor: str = "agent:executor"
    timestamp: str | None = None


@dataclass(frozen=True)
class ReviewCompleted(DomainEvent):
    """Review phase completed event.

    Published when reviewer completes successfully.
    """

    issue_number: int
    branch: str
    verdict: str
    actor: str = "agent:review"
    timestamp: str | None = None


# Dispatch-intent events (authoritative dispatch signals)


@dataclass(frozen=True)
class PlannerDispatched(DomainEvent):
    """Planner dispatch intent event.

    Authoritative signal that planner should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="plan".
    """

    issue_number: int
    branch: str
    trigger_state: str  # "claimed"
    actor: str = "system:dispatcher"
    timestamp: str | None = None


@dataclass(frozen=True)
class ExecutorDispatched(DomainEvent):
    """Executor dispatch intent event.

    Authoritative signal that executor should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="run".
    """

    issue_number: int
    branch: str
    trigger_state: str  # "in-progress"
    plan_ref: str | None = None
    audit_ref: str | None = None
    actor: str = "system:dispatcher"
    timestamp: str | None = None


@dataclass(frozen=True)
class ReviewerDispatched(DomainEvent):
    """Reviewer dispatch intent event.

    Authoritative signal that reviewer should be dispatched for an issue.
    Published by StateLabelDispatchService when trigger_name="review".
    """

    issue_number: int
    branch: str
    trigger_state: str  # "review"
    report_ref: str | None = None
    actor: str = "system:dispatcher"
    timestamp: str | None = None
