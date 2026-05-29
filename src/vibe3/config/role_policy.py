"""Centralized role policy mapping for execution roles.

This module provides a single source of truth for role-specific policies,
eliminating scattered mappings across multiple modules.
"""

from typing import Literal

# Role to config section mapping
# Note: Uses str instead of ExecutionRole because it includes "manager"
# which is not part of ExecutionRole (only planner/executor/reviewer)
ROLE_TO_SECTION: dict[str, Literal["manager", "plan", "run", "review"]] = {
    "manager": "manager",
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
}


def get_role_section(role: str) -> Literal["manager", "plan", "run", "review"]:
    """Get the config section for a given role."""
    return ROLE_TO_SECTION[role]


# Role to required ref key mapping for no-op gate
# Used by unified no-op gate to check if agent produced required ref
ROLE_TO_REQUIRED_REF_KEY: dict[str, str | None] = {
    "planner": "plan_ref",
    "executor": "report_ref",
    "reviewer": None,
    "manager": None,  # manager 不受 ref 检查约束
}


def get_role_required_ref_key(role: str) -> str | None:
    """Get the required ref key for a given role's no-op gate check.

    Returns None for roles that should skip the ref check (e.g., manager).
    """
    return ROLE_TO_REQUIRED_REF_KEY.get(role)
