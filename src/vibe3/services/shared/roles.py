"""Role policy helper functions that depend on services."""

from typing import Callable


def get_role_block_function(role: str) -> Callable[..., None]:
    """Get the block function for a given role."""
    import importlib

    _failure = importlib.import_module("vibe3.services.issue.failure")
    block_fns: dict[str, Callable[..., None]] = {
        "manager": _failure.block_manager_noop_issue,
        "planner": _failure.block_planner_noop_issue,
        "executor": _failure.block_executor_noop_issue,
        "reviewer": _failure.block_reviewer_noop_issue,
    }
    return block_fns[role]
