"""Centralized role policy mapping for execution roles.

This module provides a single source of truth for role-specific policies,
eliminating scattered mappings across multiple modules.
"""

from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from vibe3.agents.models import ExecutionRole

# Role to config section mapping
# Note: Uses str instead of ExecutionRole because it includes "manager"
# which is not part of ExecutionRole (only planner/executor/reviewer)
ROLE_TO_SECTION: dict[str, Literal["manager", "plan", "run", "review"]] = {
    "manager": "manager",
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
}


def get_role_section(
    role: "ExecutionRole | str",
) -> Literal["manager", "plan", "run", "review"]:
    """Get the config section for a given role."""
    return ROLE_TO_SECTION[role]


# Role to required ref key mapping for no-op gate
# Used by unified no-op gate to check if agent produced required ref
ROLE_TO_REQUIRED_REF_KEY: dict[str, str | None] = {
    "planner": "plan_ref",
    "executor": "report_ref",
    "reviewer": "audit_ref",
    "manager": None,  # manager 不受 ref 检查约束
}


def get_role_required_ref_key(role: "ExecutionRole | str") -> str | None:
    """Get the required ref key for a given role's no-op gate check.

    Returns None for roles that should skip the ref check (e.g., manager).
    """
    return ROLE_TO_REQUIRED_REF_KEY.get(role)


# Handoff kind to actor state key mapping
# Used by handoff recorder to write latest_actor to flow state
KIND_TO_ACTOR_KEY: dict[str, str] = {
    "plan": "planner_actor",
    "run": "executor_actor",
    "review": "reviewer_actor",
}


# Lazy import to avoid circular dependencies
def _get_block_functions() -> dict[str, Callable[..., None]]:
    """Get role-specific block functions (lazy import to avoid cycles)."""
    from vibe3.services.issue_failure_service import (
        block_executor_noop_issue,
        block_manager_noop_issue,
        block_planner_noop_issue,
        block_reviewer_noop_issue,
    )

    return {
        "manager": block_manager_noop_issue,
        "planner": block_planner_noop_issue,
        "executor": block_executor_noop_issue,
        "reviewer": block_reviewer_noop_issue,
    }


def get_role_block_function(role: "ExecutionRole | str") -> Callable[..., None]:
    """Get the block function for a given role."""
    return _get_block_functions()[role]
