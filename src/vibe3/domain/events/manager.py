"""Manager domain events.

Events for manager execution lifecycle and flow dispatching.
"""

from dataclasses import dataclass

# Import base class from parent module
from vibe3.domain.events import DomainEvent as _DomainEvent

# Re-export for convenience
DomainEvent = _DomainEvent


@dataclass(frozen=True)
class ManagerExecutionStarted(DomainEvent):
    """Manager execution started event.

    Published when manager begins processing an issue.
    """

    issue_number: int
    branch: str
    actor: str = "agent:manager"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManagerExecutionCompleted(DomainEvent):
    """Manager execution completed event.

    Published when manager finishes processing an issue successfully.
    """

    issue_number: int
    branch: str
    actor: str = "agent:manager"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManagerFlowDispatched(DomainEvent):
    """Manager flow dispatched event.

    Published when manager dispatches a new flow (task/issue).
    """

    issue_number: int
    branch: str
    tmux_session: str
    actor: str = "agent:manager"
    timestamp: str | None = None


@dataclass(frozen=True)
class ManagerFlowQueued(DomainEvent):
    """Manager flow queued event.

    Published when manager queues a flow due to capacity limits.
    """

    issue_number: int
    reason: str
    active_flows: int
    max_capacity: int
    actor: str = "system:manager"
    timestamp: str | None = None
