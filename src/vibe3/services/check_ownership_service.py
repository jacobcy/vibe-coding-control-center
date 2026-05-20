"""Worktree ownership checking for flow consistency verification."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


def check_worktree_ownership(
    store: "SQLiteClient",
    branch: str,
    flow_status: str,
    inactive_flow_statuses: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Check worktree ownership consistency for a branch.

    Args:
        store: SQLite client instance.
        branch: Branch name to check.
        flow_status: Current flow status.
        inactive_flow_statuses: Tuple of inactive flow statuses to skip.

    Returns:
        Tuple of (errors, warnings) found.
        - errors: Critical issues that prevent normal operation
        - warnings: Non-critical issues that may be intentional
    """
    if flow_status in inactive_flow_statuses:
        return [], []  # Skip inactive flows

    from vibe3.services.worktree_ownership_guard import (
        get_current_session_id,
        get_worktree_owner,
    )
    from vibe3.utils.path_helpers import find_worktree_path_for_branch

    try:
        worktree_path = find_worktree_path_for_branch(branch)
        if worktree_path is None:
            return [], []  # No worktree, skip ownership check

        owner_session = get_worktree_owner(store, str(worktree_path))
        if owner_session is None:
            # Unowned worktree with active flow
            # This is a WARNING, not an ERROR - may be intentional for manual flows
            return [], [
                f"Worktree for branch '{branch}' has no registered owner session. "
                "If this is a manually created flow, no action needed. "
                "Otherwise, check if the flow was created by standard dispatch."
            ]

        # Check if owner session is still live
        owner_tmux_session = owner_session.get("tmux_session")
        if not owner_tmux_session:
            return [], []  # Owner session has no tmux_session field (legacy)

        # Check tmux liveness
        from vibe3.agents.backends.async_launcher import has_tmux_session

        if not has_tmux_session(owner_tmux_session):
            # Orphaned ownership: session died but worktree still claimed
            # This is an ERROR - needs user action
            return [
                f"ORPHANED_OWNERSHIP: Worktree for branch '{branch}' is claimed "
                f"by dead session '{owner_tmux_session}'. "
                "The owning session has ended. Clear the stale runtime session record "
                "to reclaim this worktree."
            ], []

        # Check if current session matches owner (only if in tmux)
        current_session_id = get_current_session_id()
        if current_session_id and current_session_id != owner_tmux_session:
            # Session mismatch: different session trying to use the worktree
            # This is an ERROR - needs user action
            return [
                f"Session mismatch: Worktree for branch '{branch}' is owned by "
                f"session '{owner_tmux_session}', but current session is "
                f"'{current_session_id}'. "
                "Inspect the live runtime session and wait for it to finish "
                "before retrying."
            ], []

        return [], []  # Ownership is consistent
    except Exception as exc:
        logger.bind(domain="check", branch=branch).debug(
            f"Could not verify worktree ownership: {exc}"
        )
        return [], []  # Skip on errors (non-critical check)
