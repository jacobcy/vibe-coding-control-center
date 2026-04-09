"""Domain events for Vibe3 lifecycle.

These events represent business state changes across all execution chains.
Event-driven architecture allows loose coupling between Usecase and Service layers.

Events are organized by execution chain:
- flow_lifecycle: L3 agent chain (planner, executor, reviewer)
- governance: L1 governance service (periodic scans)
- manager: L3 manager execution (flow dispatching)
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
    ExecutionCompleted,
    ExecutorDispatched,
    FlowAborted,
    FlowBlocked,
    IssueBlocked,
    IssueFailed,
    IssueStateChanged,
    PlanCompleted,
    PlannerDispatched,
    ReportRefRequired,
    ReviewCompleted,
    ReviewerDispatched,
)
from vibe3.domain.events.governance import (  # noqa: E402
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    SupervisorExecutionCompleted,
)
from vibe3.domain.events.manager import (  # noqa: E402
    ManagerExecutionCompleted,
    ManagerExecutionStarted,
    ManagerFlowDispatched,
    ManagerFlowQueued,
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
    "IssueBlocked",
    "ReportRefRequired",
    "FlowBlocked",
    "FlowAborted",
    "PlanCompleted",
    "ReviewCompleted",
    "ExecutionCompleted",
    # L3 Dispatch-Intent Events
    "PlannerDispatched",
    "ExecutorDispatched",
    "ReviewerDispatched",
    # L1 Governance Events
    "GovernanceScanStarted",
    "GovernanceScanCompleted",
    "GovernanceDecisionRequired",
    "SupervisorExecutionCompleted",
    # L3 Manager Events
    "ManagerExecutionStarted",
    "ManagerExecutionCompleted",
    "ManagerFlowDispatched",
    "ManagerFlowQueued",
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
    "issue_state_changed": IssueStateChanged,
    "issue_failed": IssueFailed,
    "issue_blocked": IssueBlocked,
    "report_ref_required": ReportRefRequired,
    "flow_blocked": FlowBlocked,
    "flow_aborted": FlowAborted,
    "plan_completed": PlanCompleted,
    "review_completed": ReviewCompleted,
    "execution_completed": ExecutionCompleted,
    # L3 Dispatch-Intent
    "planner_dispatched": PlannerDispatched,
    "executor_dispatched": ExecutorDispatched,
    "reviewer_dispatched": ReviewerDispatched,
    # L1 Governance
    "governance_scan_started": GovernanceScanStarted,
    "governance_scan_completed": GovernanceScanCompleted,
    "governance_decision_required": GovernanceDecisionRequired,
    "supervisor_execution_completed": SupervisorExecutionCompleted,
    # L3 Manager
    "manager_execution_started": ManagerExecutionStarted,
    "manager_execution_completed": ManagerExecutionCompleted,
    "manager_flow_dispatched": ManagerFlowDispatched,
    "manager_flow_queued": ManagerFlowQueued,
    # L2 Supervisor Apply
    "supervisor_issue_identified": SupervisorIssueIdentified,
    "supervisor_prompt_rendered": SupervisorPromptRendered,
    "supervisor_apply_dispatched": SupervisorApplyDispatched,
    "supervisor_apply_started": SupervisorApplyStarted,
    "supervisor_apply_completed": SupervisorApplyCompleted,
    "supervisor_apply_delegated": SupervisorApplyDelegated,
}
