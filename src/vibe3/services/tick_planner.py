"""TickPlanner service - creates execution plans from tick requests."""

from typing import Any

from vibe3.models.tick import TickPlan, TickRequest


class TickPlanner:
    """Service for creating tick execution plans.

    TickPlanner is responsible for:
    - Resolving governance material (auto-rotate or explicit)
    - Resolving supervisor issues (scan candidates or explicit)
    - Creating TickPlan from TickRequest

    TickPlanner does NOT:
    - Execute governance/supervisor (that's TickDispatcher's job)
    - Access GitHub API (that's done by dispatcher during execution)

    The service is intentionally thin - planning logic is delegated to
    TickPlan.from_request() to keep the service focused on orchestration.
    """

    def __init__(self, config: Any):
        """Initialize TickPlanner with orchestra configuration.

        Args:
            config: Orchestra configuration (OrchestraConfig or None for testing)
        """
        self.config = config

    def plan(self, request: TickRequest, tick_count: int = 0) -> TickPlan:
        """Create execution plan from tick request.

        Args:
            request: Tick request with user intent
            tick_count: Current tick count (for material rotation)

        Returns:
            Resolved TickPlan with concrete parameters
        """
        return TickPlan.from_request(request, self.config, tick_count)
