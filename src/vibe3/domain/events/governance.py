"""Governance domain events.

Events for governance service lifecycle and periodic scans.
"""

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class GovernanceScanStarted(DomainEvent):
    """Governance scan started event.

    Published when periodic governance scan begins.
    """

    tick_count: int
    execution_count: int = 0  # Independent counter for material rotation
    material_override: str | None = None  # Optional material role override
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
