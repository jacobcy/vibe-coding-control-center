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
    FlowAborted,
    FlowBlocked,
    # L1 Governance Events
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    IssueBlocked,
    IssueFailed,
    IssueStateChanged,
    PlanCompleted,
    ReportRefRequired,
    ReviewCompleted,
    # L2 Supervisor Apply Events
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorExecutionCompleted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)
from vibe3.domain.handlers import register_event_handlers
from vibe3.domain.publisher import get_publisher, publish, subscribe

__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
    "IssueStateChanged",
    "IssueFailed",
    "IssueBlocked",
    "ReportRefRequired",
    "FlowBlocked",
    "FlowAborted",
    "PlanCompleted",
    "ReviewCompleted",
    # L1 Governance Events
    "GovernanceScanStarted",
    "GovernanceScanCompleted",
    "GovernanceDecisionRequired",
    "SupervisorExecutionCompleted",
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
