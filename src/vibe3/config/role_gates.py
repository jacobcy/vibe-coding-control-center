"""Role-specific gate configurations for worktree requirements."""

from vibe3.models import WorktreeRequirement

MANAGER_GATE_CONFIG = WorktreeRequirement.PERMANENT
GOVERNANCE_GATE_CONFIG = WorktreeRequirement.NONE
PLANNER_GATE_CONFIG = WorktreeRequirement.PERMANENT
EXECUTOR_GATE_CONFIG = WorktreeRequirement.PERMANENT
REVIEWER_GATE_CONFIG = WorktreeRequirement.PERMANENT
SUPERVISOR_IDENTIFY_GATE_CONFIG = WorktreeRequirement.NONE
SUPERVISOR_APPLY_GATE_CONFIG = WorktreeRequirement.TEMPORARY
