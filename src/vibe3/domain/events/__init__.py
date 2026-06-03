"""Domain events for Vibe3 lifecycle.

These events represent business state changes across all execution chains.
Event-driven architecture allows loose coupling between Usecase and Service layers.

Events are organized by execution chain:
- flow_lifecycle: L3 agent chain (planner, executor, reviewer)
- governance: L1 governance service (periodic scans)
- supervisor_apply: L2 supervisor handoff chain (lightweight governance execution)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

# Import from submodules
from vibe3.domain.events.flow_lifecycle import (  # noqa: E402
    ExecutorDispatchIntent,
    IssueFailed,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
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

from .base import DomainEvent

__all__ = [
    # Base
    "DomainEvent",
    # L3 Flow Lifecycle Events
    "IssueFailed",
    # L3 Dispatch-Intent Events
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
]

# Event type registry
EVENT_TYPES = {
    # L3 Flow Lifecycle
    "issue_failed": IssueFailed,
    # L3 Dispatch-Intent
    "manager_dispatch_intent": ManagerDispatchIntent,
    "planner_dispatch_intent": PlannerDispatchIntent,
    "executor_dispatch_intent": ExecutorDispatchIntent,
    "reviewer_dispatch_intent": ReviewerDispatchIntent,
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
