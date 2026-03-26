"""Helpers for resolving flow close targets."""

from typing import Any

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.flow import CloseTargetDecision


def resolve_close_target(store: Any, branch: str) -> CloseTargetDecision:
    """Resolve target branch for flow close with explicit rules."""
    dependency_store = store
    if not hasattr(dependency_store, "get_flow_dependents"):
        dependency_store = SQLiteClient()

    try:
        dependents = dependency_store.get_flow_dependents(branch)
    except Exception as e:
        logger.warning(f"Failed to query flow dependents: {e}")
        dependents = []

    if len(dependents) == 1:
        return CloseTargetDecision(
            target_branch=dependents[0],
            should_pull=False,
            reason="Single active dependent flow exists",
        )

    if len(dependents) > 1:
        logger.warning(
            f"Multiple active flows depend on '{branch}': {', '.join(dependents)}\n"
            f"Use 'vibe3 flow switch <branch>' to switch to specific branch"
        )

    return CloseTargetDecision(
        target_branch="main",
        should_pull=True,
        reason="No single active dependent - returning to safe branch",
    )
