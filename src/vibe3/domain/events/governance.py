"""Governance domain events.

Events for governance service lifecycle and periodic scans.
"""

from dataclasses import dataclass

# Import base class from parent module
from vibe3.domain.events import DomainEvent as _DomainEvent

# Re-export for convenience
DomainEvent = _DomainEvent


@dataclass(frozen=True)
class GovernanceScanStarted(DomainEvent):
    """Governance scan started event.

    Published when periodic governance scan begins.
    """

    tick_count: int
    actor: str = "system:governance"
    timestamp: str | None = None


@dataclass(frozen=True)
class GovernanceScanCompleted(DomainEvent):
    """Governance scan completed event.

    Published when periodic governance scan finishes successfully.
    """

    tick_count: int
    active_flows: int
    suggested_issues: int
    actor: str = "system:governance"
    timestamp: str | None = None


@dataclass(frozen=True)
class GovernanceDecisionRequired(DomainEvent):
    """Governance decision required event.

    Published when governance scan detects issues requiring manual decision.
    """

    issue_number: int
    reason: str
    suggested_action: str | None = None
    actor: str = "system:governance"
    timestamp: str | None = None
