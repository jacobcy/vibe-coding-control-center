"""Domain module - Event-driven architecture for Vibe3 execution chains.

This module provides domain events for all execution layers:
- L1: Governance service (periodic scans)
- L2: Supervisor + Apply chain (lightweight governance execution)
- L3: Agent chain (full development workflow)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

from vibe3.domain.events import (
    # Base
    DomainEvent,
    # L3 Flow Lifecycle Events
    # L1 Governance Events
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    IssueFailed,
    IssueStateChanged,
    # L2 Supervisor Apply Events
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)


def register_event_handlers() -> None:
    """Register domain event handlers lazily to avoid import cycles."""
    from vibe3.domain.handlers import (
        register_event_handlers as _register_event_handlers,
    )

    _register_event_handlers()


def get_publisher():  # type: ignore[no-untyped-def]
    """Return the global domain event publisher lazily."""
    from vibe3.domain.publisher import get_publisher as _get_publisher

    return _get_publisher()


def publish(event):  # type: ignore[no-untyped-def]
    """Publish a domain event lazily."""
    from vibe3.domain.publisher import publish as _publish

    return _publish(event)


def subscribe(event_type, handler):  # type: ignore[no-untyped-def]
    """Subscribe a handler lazily."""
    from vibe3.domain.publisher import subscribe as _subscribe

    return _subscribe(event_type, handler)


__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
    "IssueStateChanged",
    "IssueFailed",
    # L1 Governance Events
    "GovernanceScanStarted",
    "GovernanceScanCompleted",
    "GovernanceDecisionRequired",
    # L2 Supervisor Apply Events
    "SupervisorIssueIdentified",
    "SupervisorPromptRendered",
    "SupervisorApplyDispatched",
    "SupervisorApplyStarted",
    "SupervisorApplyCompleted",
    "SupervisorApplyDelegated",
    # Publisher
    "get_publisher",
    "publish",
    "subscribe",
    # Handlers
    "register_event_handlers",
]
