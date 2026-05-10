"""Tick request and plan models for unified scan/heartbeat architecture."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TickSource(str, Enum):
    """Source of tick execution."""

    MANUAL_SCAN = "manual_scan"
    HEARTBEAT = "heartbeat"


class TickPhase(str, Enum):
    """Execution phases within a tick."""

    GOVERNANCE = "governance"
    SUPERVISOR = "supervisor"


class TickRequest(BaseModel):
    """Request to execute a manual or automatic tick.

    Attributes:
        source: Where this tick originated (manual scan or heartbeat)
        tick_id: Tick number (0 for manual, 1..N for heartbeat)
        phases: Which phases to execute (governance/supervisor)
        governance_material: Optional explicit material override
        supervisor_issue_numbers: Optional explicit issue list
        dry_run: Preview mode without actual execution
    """

    source: TickSource
    tick_id: int = Field(default=0, ge=0)
    phases: list[TickPhase] = Field(
        default_factory=lambda: [TickPhase.GOVERNANCE, TickPhase.SUPERVISOR]
    )
    governance_material: str | None = None
    supervisor_issue_numbers: list[int] = Field(default_factory=list)
    dry_run: bool = False

    model_config = {"frozen": True}


class TickPlan(BaseModel):
    """Execution plan derived from TickRequest.

    Represents the resolved execution plan with concrete parameters
    after applying config, material rotation, and issue selection.

    Attributes:
        governance_enabled: Whether governance phase will execute
        governance_material: Resolved material (auto or explicit)
        supervisor_enabled: Whether supervisor phase will execute
        supervisor_issues: Resolved issue list (scanned or explicit)
        dry_run: Preview mode
    """

    governance_enabled: bool
    governance_material: str | None = None
    supervisor_enabled: bool
    supervisor_issues: list[int] = Field(default_factory=list)
    dry_run: bool = False

    @classmethod
    def from_request(
        cls,
        request: TickRequest,
        config: Any,
        tick_count: int = 0,
    ) -> "TickPlan":
        """Create execution plan from tick request.

        Args:
            request: Tick request with user intent
            config: Orchestra configuration (can be None for testing)
            tick_count: Current tick count (for material rotation)

        Returns:
            Resolved TickPlan with concrete parameters
        """
        # Resolve governance
        governance_enabled = TickPhase.GOVERNANCE in request.phases
        governance_material = None
        if governance_enabled:
            if request.governance_material:
                # Use explicit material
                governance_material = request.governance_material
            elif config is not None:
                # Auto-select via rotation (import here to avoid circular dep)
                from vibe3.roles.governance import _resolve_governance_material

                governance_material = _resolve_governance_material(config, tick_count)

        # Resolve supervisor
        supervisor_enabled = TickPhase.SUPERVISOR in request.phases
        supervisor_issues = request.supervisor_issue_numbers.copy()

        return cls(
            governance_enabled=governance_enabled,
            governance_material=governance_material,
            supervisor_enabled=supervisor_enabled,
            supervisor_issues=supervisor_issues,
            dry_run=request.dry_run,
        )

    model_config = {"frozen": True}
