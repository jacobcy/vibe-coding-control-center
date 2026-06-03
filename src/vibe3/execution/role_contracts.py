"""Role dispatch contracts — re-exported from lower-layer homes."""

from vibe3.config.role_gates import (
    EXECUTOR_GATE_CONFIG,
    GOVERNANCE_GATE_CONFIG,
    MANAGER_GATE_CONFIG,
    PLANNER_GATE_CONFIG,
    REVIEWER_GATE_CONFIG,
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
)
from vibe3.models.worktree import WorktreeRequirement

__all__ = [
    "WorktreeRequirement",
    "EXECUTOR_GATE_CONFIG",
    "GOVERNANCE_GATE_CONFIG",
    "MANAGER_GATE_CONFIG",
    "PLANNER_GATE_CONFIG",
    "REVIEWER_GATE_CONFIG",
    "SUPERVISOR_APPLY_GATE_CONFIG",
    "SUPERVISOR_IDENTIFY_GATE_CONFIG",
]
