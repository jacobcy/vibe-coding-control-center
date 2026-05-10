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

Handlers are automatically registered via @register_handler decorator
at module import time.

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""

# Import handler modules to trigger @register_handler decorator registration
from vibe3.domain.handlers import (
    dispatch as dispatch,
)
from vibe3.domain.handlers import (
    flow_lifecycle as flow_lifecycle,
)
from vibe3.domain.handlers import (
    governance_scan as governance_scan,
)
from vibe3.domain.handlers import (
    issue_state_dispatch as issue_state_dispatch,
)
from vibe3.domain.handlers import (
    supervisor_scan as supervisor_scan,
)


def register_event_handlers() -> None:
    """Register all event handlers with the global publisher.

    Note: With @register_handler decorator, handlers are registered
    at module import time. This function exists for backward compatibility
    and to ensure all handler modules are imported.

    Registration happens automatically when modules are imported above.
    """


__all__ = [
    "register_event_handlers",
]
