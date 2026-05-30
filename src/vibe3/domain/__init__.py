"""Domain module - Event-driven architecture for Vibe3 execution chains.

This module provides domain events for all execution layers:
- L1: Governance service (periodic scans)
- L2: Supervisor + Apply chain (lightweight governance execution)
- L3: Agent chain (full development workflow)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

from typing import TYPE_CHECKING, Callable

from vibe3.domain.events import (
    # Base
    DomainEvent,
    # L3 Flow Lifecycle Events
    # L1 Governance Events
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    IssueFailed,
    # L2 Supervisor Apply Events
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)

# Import orchestration components lazily to avoid circular imports
# FlowManager, GlobalDispatchCoordinator, and FailedGate are available through
# __getattr__ for runtime access
if TYPE_CHECKING:
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.failed_gate import FailedGate
    from vibe3.domain.flow_manager import FlowManager

if TYPE_CHECKING:
    from vibe3.domain.publisher import EventPublisher


def register_event_handlers() -> None:
    """Register domain event handlers lazily to avoid import cycles."""
    from vibe3.domain.handlers import (
        register_event_handlers as _register_event_handlers,
    )

    _register_event_handlers()


def get_publisher() -> "EventPublisher":
    """Return the global domain event publisher lazily."""
    from vibe3.domain.publisher import get_publisher as _get_publisher

    return _get_publisher()


def publish(event: DomainEvent) -> None:
    """Publish a domain event lazily."""
    from vibe3.domain.publisher import publish as _publish

    return _publish(event)


def subscribe(event_type: str, handler: "Callable[[DomainEvent], None]") -> None:
    """Subscribe a handler lazily."""
    from vibe3.domain.publisher import subscribe as _subscribe

    return _subscribe(event_type, handler)


def __getattr__(name: str) -> type:
    """Lazy import for heavy modules to avoid circular dependencies."""
    if name == "FlowManager":
        from vibe3.domain.flow_manager import FlowManager

        return FlowManager
    if name == "GlobalDispatchCoordinator":
        from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator

        return GlobalDispatchCoordinator
    if name == "FailedGate":
        from vibe3.domain.failed_gate import FailedGate

        return FailedGate
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
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
    # Orchestration
    "FlowManager",
    "GlobalDispatchCoordinator",
    "FailedGate",
    # Publisher
    "get_publisher",
    "publish",
    "subscribe",
    # Handlers
    "register_event_handlers",
]
