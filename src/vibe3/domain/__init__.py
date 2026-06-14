"""Domain module - Event-driven architecture for Vibe3 execution chains.

This module provides domain events for all execution layers:
- L1: Governance service (periodic scans)
- L2: Supervisor + Apply chain (lightweight governance execution)
- L3: Agent chain (full development workflow)

Reference: docs/standards/v3/worktree-lifecycle-standard.md
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.domain.dispatch_coordinator import (
        MAX_INTENTS_PER_TICK,
        GlobalDispatchCoordinator,
    )
    from vibe3.domain.event_rules import (
        EventRule,
        build_action_handlers,
        evaluate_rules,
        expand_template,
        load_rules,
    )
    from vibe3.domain.events.base import DomainEvent
    from vibe3.domain.events.flow_lifecycle import (
        ControlPlaneEventPublished,
        ExecutorDispatchIntent,
        FlowBlocked,
        FlowCompleted,
        IssueFailed,
        ManagerDispatchIntent,
        ManualPlanIntent,
        ManualReviewIntent,
        ManualRunIntent,
        PlannerDispatchIntent,
        PRMerged,
        ReviewerDispatchIntent,
    )
    from vibe3.domain.events.governance import (
        GovernanceDecisionRequired,
        GovernanceScanCompleted,
        GovernanceScanStarted,
    )
    from vibe3.domain.events.policy import PolicyChanged
    from vibe3.domain.events.supervisor_apply import (
        SupervisorApplyCompleted,
        SupervisorApplyDelegated,
        SupervisorApplyDispatched,
        SupervisorApplyStarted,
        SupervisorIssueIdentified,
        SupervisorPromptRendered,
    )
    from vibe3.domain.failed_gate import FailedGate, GateResult, GateStatus
    from vibe3.domain.flow_manager import FlowManager
    from vibe3.domain.handlers.manual_dispatch import get_pending_result
    from vibe3.domain.orchestration_facade import OrchestrationFacade
    from vibe3.domain.protocols.dispatch_protocols import (
        CapacityServiceProtocol,
        CheckServiceProtocol,
        FlowServiceProtocol,
        LabelDispatchCallable,
    )
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.domain.protocols.runtime_protocols import ServiceBase
    from vibe3.domain.publisher import (
        EventHandler,
        EventPublisher,
        get_publisher,
        publish,
        subscribe,
    )
    from vibe3.domain.qualify_gate import QualifyGateService
    from vibe3.domain.role_resolver import find_role_for_state

_LAZY_IMPORTS: dict[str, str] = {
    # Events - base
    "DomainEvent": "vibe3.domain.events.base",
    # Events - flow lifecycle
    "ControlPlaneEventPublished": "vibe3.domain.events.flow_lifecycle",
    "IssueFailed": "vibe3.domain.events.flow_lifecycle",
    "FlowBlocked": "vibe3.domain.events.flow_lifecycle",
    "FlowCompleted": "vibe3.domain.events.flow_lifecycle",
    "PRMerged": "vibe3.domain.events.flow_lifecycle",
    "ManagerDispatchIntent": "vibe3.domain.events.flow_lifecycle",
    "ManualPlanIntent": "vibe3.domain.events.flow_lifecycle",
    "ManualRunIntent": "vibe3.domain.events.flow_lifecycle",
    "ManualReviewIntent": "vibe3.domain.events.flow_lifecycle",
    "PlannerDispatchIntent": "vibe3.domain.events.flow_lifecycle",
    "ExecutorDispatchIntent": "vibe3.domain.events.flow_lifecycle",
    "ReviewerDispatchIntent": "vibe3.domain.events.flow_lifecycle",
    # Events - governance
    "GovernanceScanStarted": "vibe3.domain.events.governance",
    "GovernanceScanCompleted": "vibe3.domain.events.governance",
    "GovernanceDecisionRequired": "vibe3.domain.events.governance",
    # Events - policy
    "PolicyChanged": "vibe3.domain.events.policy",
    # Events - supervisor apply
    "SupervisorApplyCompleted": "vibe3.domain.events.supervisor_apply",
    "SupervisorApplyDelegated": "vibe3.domain.events.supervisor_apply",
    "SupervisorApplyDispatched": "vibe3.domain.events.supervisor_apply",
    "SupervisorApplyStarted": "vibe3.domain.events.supervisor_apply",
    "SupervisorIssueIdentified": "vibe3.domain.events.supervisor_apply",
    "SupervisorPromptRendered": "vibe3.domain.events.supervisor_apply",
    # Orchestration
    "FlowManager": "vibe3.domain.flow_manager",
    "GlobalDispatchCoordinator": "vibe3.domain.dispatch_coordinator",
    "FailedGate": "vibe3.domain.failed_gate",
    # Protocols
    "CapacityServiceProtocol": "vibe3.domain.protocols.dispatch_protocols",
    "CheckServiceProtocol": "vibe3.domain.protocols.dispatch_protocols",
    "FlowServiceProtocol": "vibe3.domain.protocols.dispatch_protocols",
    "LabelDispatchCallable": "vibe3.domain.protocols.dispatch_protocols",
    "FlowManagerProtocol": "vibe3.domain.protocols.flow_protocols",
    "ServiceBase": "vibe3.domain.protocols.runtime_protocols",
    # Additional domain classes
    "GateResult": "vibe3.domain.failed_gate",
    "GateStatus": "vibe3.domain.failed_gate",
    "MAX_INTENTS_PER_TICK": "vibe3.domain.dispatch_coordinator",
    "OrchestrationFacade": "vibe3.domain.orchestration_facade",
    "QualifyGateService": "vibe3.domain.qualify_gate",
    "find_role_for_state": "vibe3.domain.role_resolver",
    # Publisher
    "EventPublisher": "vibe3.domain.publisher",
    "EventHandler": "vibe3.domain.publisher",
    "publish": "vibe3.domain.publisher",
    "publish_and_wait": "vibe3.domain.publisher",
    "subscribe": "vibe3.domain.publisher",
    "get_publisher": "vibe3.domain.publisher",
    # Event rules
    "EventRule": "vibe3.domain.event_rules",
    "build_action_handlers": "vibe3.domain.event_rules",
    "evaluate_rules": "vibe3.domain.event_rules",
    "expand_template": "vibe3.domain.event_rules",
    "load_rules": "vibe3.domain.event_rules",
    "get_pending_result": "vibe3.domain.handlers.manual_dispatch",
}


def register_event_handlers() -> None:
    """Register domain event handlers lazily to avoid import cycles."""
    import vibe3.domain.handlers  # noqa: F401 triggers @register_handler at import time


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
    "ControlPlaneEventPublished",
    "IssueFailed",
    "FlowBlocked",
    "FlowCompleted",
    "PRMerged",
    "ManagerDispatchIntent",
    "ManualPlanIntent",
    "ManualRunIntent",
    "ManualReviewIntent",
    "PlannerDispatchIntent",
    "ExecutorDispatchIntent",
    "ReviewerDispatchIntent",
    # L1 Governance Events
    "GovernanceScanStarted",
    "GovernanceScanCompleted",
    "GovernanceDecisionRequired",
    # Policy Events
    "PolicyChanged",
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
    "GateResult",
    "GateStatus",
    "MAX_INTENTS_PER_TICK",
    "OrchestrationFacade",
    "QualifyGateService",
    "find_role_for_state",
    # Protocols
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "FlowManagerProtocol",
    "LabelDispatchCallable",
    "ServiceBase",
    # Publisher
    "EventPublisher",
    "EventHandler",
    "get_publisher",
    "publish",
    "publish_and_wait",
    "subscribe",
    # Event rules
    "EventRule",
    "build_action_handlers",
    "evaluate_rules",
    "expand_template",
    "load_rules",
    # Handlers
    "register_event_handlers",
    "get_pending_result",
]
