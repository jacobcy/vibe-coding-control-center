"""Domain event handlers.

Event handlers respond to domain events and perform the actual business operations.
They bridge the gap between Usecase layer (event publishers) and Service layer.

Handlers are organized by execution chain:
- flow_lifecycle: L3 agent chain handlers (planner, executor, reviewer)
- governance: L1 governance service handlers (periodic scans)
- issue_state_dispatch: L3 issue-state role dispatch handlers
- supervisor_apply: L2 supervisor handoff handlers (lightweight governance execution)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

from vibe3.domain.handlers.dispatch import register_dispatch_handlers
from vibe3.domain.handlers.flow_lifecycle import register_flow_lifecycle_handlers
from vibe3.domain.handlers.governance import register_governance_handlers
from vibe3.domain.handlers.issue_state_dispatch import (
    register_issue_state_dispatch_handlers,
)
from vibe3.domain.handlers.supervisor_apply import register_supervisor_apply_handlers


def register_event_handlers() -> None:
    """Register all event handlers with the global publisher.

    This function should be called at application startup to ensure
    all event handlers are properly registered.

    Registration order:
    1. L1 Governance handlers
    2. L2 Supervisor Apply handlers
    3. L3 Flow Lifecycle handlers
    4. L3 Issue-state role dispatch handlers
    5. L3 Dispatch handlers
    """
    register_governance_handlers()
    register_supervisor_apply_handlers()
    register_flow_lifecycle_handlers()
    register_issue_state_dispatch_handlers()
    register_dispatch_handlers()


__all__ = [
    "register_event_handlers",
]
