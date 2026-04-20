"""Domain event handlers.

Event handlers respond to domain events and perform the actual business operations.
They bridge the gap between Usecase layer (event publishers) and Service layer.

Handlers are organized by execution chain:
- flow_lifecycle: L3 agent chain handlers (planner, executor, reviewer)
- issue_state_dispatch: L3 issue-state role dispatch handlers
- dispatch: L3 planner/executor/reviewer dispatch-intent handlers
- governance_scan: L1 governance scan handler (GovernanceScanStarted)
- supervisor_scan: L2 supervisor apply handler (SupervisorIssueIdentified)

OrchestrationFacade is a pure observation layer: it publishes events only.
Execution assembly for governance and supervisor happens in these handlers.

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

from vibe3.domain.handlers.dependency_wake_up import (
    register_dependency_wake_up_handlers,
)
from vibe3.domain.handlers.dispatch import register_dispatch_handlers
from vibe3.domain.handlers.flow_lifecycle import register_flow_lifecycle_handlers
from vibe3.domain.handlers.governance_scan import register_governance_scan_handlers
from vibe3.domain.handlers.issue_state_dispatch import (
    register_issue_state_dispatch_handlers,
)
from vibe3.domain.handlers.supervisor_scan import register_supervisor_scan_handlers


def register_event_handlers() -> None:
    """Register all event handlers with the global publisher.

    This function should be called at application startup to ensure
    all event handlers are properly registered.

    Registration order:
    1. L3 Flow Lifecycle handlers
    2. L3 Issue-state role dispatch handlers
    3. L3 Dispatch handlers (planner/executor/reviewer)
    4. L3 Dependency wake-up handler
    5. L1 Governance scan handler
    6. L2 Supervisor scan handler
    """
    register_flow_lifecycle_handlers()
    register_issue_state_dispatch_handlers()
    register_dispatch_handlers()
    register_dependency_wake_up_handlers()
    register_governance_scan_handlers()
    register_supervisor_scan_handlers()


__all__ = [
    "register_event_handlers",
]
