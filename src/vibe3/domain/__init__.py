"""Domain module - Event-driven architecture for Vibe3 execution chains.

This module provides domain events for all execution layers:
- L1: Governance service (periodic scans)
- L2: Supervisor + Apply chain (lightweight governance execution)
- L3: Agent chain (full development workflow)

Reference: docs/standards/v3/worktree-lifecycle-standard.md
"""

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.events import (
        DomainEvent,
        ExecutorDispatchIntent,
        GovernanceDecisionRequired,
        GovernanceScanCompleted,
        GovernanceScanStarted,
        IssueFailed,
        ManagerDispatchIntent,
        PlannerDispatchIntent,
        ReviewerDispatchIntent,
        SupervisorApplyCompleted,
        SupervisorApplyDelegated,
        SupervisorApplyDispatched,
        SupervisorApplyStarted,
        SupervisorIssueIdentified,
        SupervisorPromptRendered,
    )
    from vibe3.domain.failed_gate import FailedGate
    from vibe3.domain.flow_manager import FlowManager
    from vibe3.domain.publisher import EventPublisher
    from vibe3.domain.state_machine import (
        STATE_LABEL_META,
        VIBE_TASK_LABEL,
        validate_transition,
    )

_LAZY_IMPORTS: dict[str, str] = {
    # Events
    "DomainEvent": "vibe3.domain.events",
    "GovernanceDecisionRequired": "vibe3.domain.events",
    "GovernanceScanCompleted": "vibe3.domain.events",
    "GovernanceScanStarted": "vibe3.domain.events",
    "IssueFailed": "vibe3.domain.events",
    "ManagerDispatchIntent": "vibe3.domain.events",
    "PlannerDispatchIntent": "vibe3.domain.events",
    "ExecutorDispatchIntent": "vibe3.domain.events",
    "ReviewerDispatchIntent": "vibe3.domain.events",
    "SupervisorApplyCompleted": "vibe3.domain.events",
    "SupervisorApplyDelegated": "vibe3.domain.events",
    "SupervisorApplyDispatched": "vibe3.domain.events",
    "SupervisorApplyStarted": "vibe3.domain.events",
    "SupervisorIssueIdentified": "vibe3.domain.events",
    "SupervisorPromptRendered": "vibe3.domain.events",
    # Orchestration
    "FlowManager": "vibe3.domain.flow_manager",
    "GlobalDispatchCoordinator": "vibe3.domain.dispatch_coordinator",
    "FailedGate": "vibe3.domain.failed_gate",
    # State machine
    "STATE_LABEL_META": "vibe3.models.state_machine",
    "VIBE_TASK_LABEL": "vibe3.models.state_machine",
    "validate_transition": "vibe3.models.state_machine",
    # Publisher
    "EventPublisher": "vibe3.domain.publisher",
}


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


def publish(event: "DomainEvent") -> None:
    """Publish a domain event lazily."""
    from vibe3.domain.publisher import publish as _publish

    return _publish(event)


def subscribe(event_type: str, handler: "Callable[[DomainEvent], None]") -> None:
    """Subscribe a handler lazily."""
    from vibe3.domain.publisher import subscribe as _subscribe

    return _subscribe(event_type, handler)


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
    "IssueFailed",
    "ManagerDispatchIntent",
    "PlannerDispatchIntent",
    "ExecutorDispatchIntent",
    "ReviewerDispatchIntent",
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
    # State machine
    "STATE_LABEL_META",
    "VIBE_TASK_LABEL",
    "validate_transition",
    # Orchestration
    "FlowManager",
    "GlobalDispatchCoordinator",
    "FailedGate",
    # Publisher
    "EventPublisher",
    "get_publisher",
    "publish",
    "subscribe",
    # Handlers
    "register_event_handlers",
]
