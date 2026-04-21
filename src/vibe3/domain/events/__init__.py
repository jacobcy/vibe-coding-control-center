"""Domain events for Vibe3 lifecycle.

These events represent business state changes across all execution chains.
Event-driven architecture allows loose coupling between Usecase and Service layers.

Events are organized by execution chain:
- flow_lifecycle: L3 agent chain (planner, executor, reviewer)
- governance: L1 governance service (periodic scans)
- supervisor_apply: L2 supervisor handoff chain (lightweight governance execution)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""

    pass


# Import from submodules
from vibe3.domain.events.flow_lifecycle import (  # noqa: E402
    DependencySatisfied,
    ExecutorDispatched,  # Backward compatibility alias
    ExecutorDispatchIntent,
    IssueFailed,
    IssueStateChanged,
    ManagerDispatched,  # Backward compatibility alias
    ManagerDispatchIntent,
    PlannerDispatched,  # Backward compatibility alias
    PlannerDispatchIntent,
    ReviewerDispatched,  # Backward compatibility alias
    ReviewerDispatchIntent,
)
from vibe3.domain.events.governance import (  # noqa: E402
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
)
from vibe3.domain.events.supervisor_apply import (  # noqa: E402
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)

__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
    "IssueStateChanged",
    "IssueFailed",
    # L3 Dispatch-Intent Events (new names)
    "ManagerDispatchIntent",
    "PlannerDispatchIntent",
    "ExecutorDispatchIntent",
    "ReviewerDispatchIntent",
    # L3 Dispatch-Intent Events (backward compatibility)
    "ManagerDispatched",
    "PlannerDispatched",
    "ExecutorDispatched",
    "ReviewerDispatched",
    # L3 Dependency Events
    "DependencySatisfied",
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
]

# Event type registry with backward compatibility
EVENT_TYPES = {
    # L3 Flow Lifecycle
    "issue_state_changed": IssueStateChanged,
    "issue_failed": IssueFailed,
    # L3 Dispatch-Intent (new names)
    "manager_dispatch_intent": ManagerDispatchIntent,
    "planner_dispatch_intent": PlannerDispatchIntent,
    "executor_dispatch_intent": ExecutorDispatchIntent,
    "reviewer_dispatch_intent": ReviewerDispatchIntent,
    # L3 Dispatch-Intent (backward compatibility)
    "manager_dispatched": ManagerDispatchIntent,
    "planner_dispatched": PlannerDispatchIntent,
    "executor_dispatched": ExecutorDispatchIntent,
    "reviewer_dispatched": ReviewerDispatchIntent,
    # L3 Dependency
    "dependency_satisfied": DependencySatisfied,
    # L1 Governance
    "governance_scan_started": GovernanceScanStarted,
    "governance_scan_completed": GovernanceScanCompleted,
    "governance_decision_required": GovernanceDecisionRequired,
    # L2 Supervisor Apply
    "supervisor_issue_identified": SupervisorIssueIdentified,
    "supervisor_prompt_rendered": SupervisorPromptRendered,
    "supervisor_apply_dispatched": SupervisorApplyDispatched,
    "supervisor_apply_started": SupervisorApplyStarted,
    "supervisor_apply_completed": SupervisorApplyCompleted,
    "supervisor_apply_delegated": SupervisorApplyDelegated,
}
