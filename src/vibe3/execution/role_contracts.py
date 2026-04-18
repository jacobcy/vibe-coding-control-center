"""Role dispatch contracts for unified role execution."""

from enum import Enum


class WorktreeRequirement(str, Enum):
    """Worktree requirement for a role execution."""

    NONE = "none"  # No worktree needed (governance)
    PERMANENT = "permanent"  # Permanent worktree (manager)
    TEMPORARY = "temporary"  # Temporary worktree (supervisor apply)


# Role-specific gate configurations
MANAGER_GATE_CONFIG = WorktreeRequirement.PERMANENT
GOVERNANCE_GATE_CONFIG = WorktreeRequirement.NONE
PLANNER_GATE_CONFIG = WorktreeRequirement.PERMANENT
EXECUTOR_GATE_CONFIG = WorktreeRequirement.PERMANENT
REVIEWER_GATE_CONFIG = WorktreeRequirement.PERMANENT
SUPERVISOR_IDENTIFY_GATE_CONFIG = WorktreeRequirement.NONE
SUPERVISOR_APPLY_GATE_CONFIG = WorktreeRequirement.TEMPORARY
