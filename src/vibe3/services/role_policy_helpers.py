"""Role policy helper functions that depend on services."""

from typing import Any

from vibe3.services.issue_failure_service import (
    block_executor_noop_issue,
    block_manager_noop_issue,
    block_planner_noop_issue,
    block_reviewer_noop_issue,
)


def get_role_block_function(role: str) -> Any:
    """Get the block function for a given role."""
    block_fns: dict[str, Any] = {
        "manager": block_manager_noop_issue,
        "planner": block_planner_noop_issue,
        "executor": block_executor_noop_issue,
        "reviewer": block_reviewer_noop_issue,
    }
    return block_fns[role]
