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


def get_role_pre_gate_callback(
    role: "ExecutionRole",
) -> Callable[..., None] | None:
    """Get role-specific callback that must run before the gate.

    Currently only reviewer has a pre_gate_callback to process audit_ref.
    Returns None for other roles.
    """
    if role != "reviewer":
        return None

    # Lazy import to avoid circular dependency
    from vibe3.roles.review import _process_review_sync_result

    return _process_review_sync_result
