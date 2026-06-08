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
# Use `_` alias to suppress Ruff F401 (unused import) warnings
from vibe3.domain.handlers import dispatch as _dispatch
from vibe3.domain.handlers import flow_lifecycle as _flow_lifecycle
from vibe3.domain.handlers import governance_scan as _governance_scan
from vibe3.domain.handlers import issue_state_dispatch as _issue_state_dispatch
from vibe3.domain.handlers import supervisor_scan as _supervisor_scan

# Store modules in private tuple to prevent Ruff from flagging as unused
# (intentionally not accessed - purpose is to keep module references alive)
_HANDLER_MODULES = (
    _dispatch,
    _flow_lifecycle,
    _governance_scan,
    _issue_state_dispatch,
    _supervisor_scan,
)
