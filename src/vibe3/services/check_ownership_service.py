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
) -> list[str]:
    """Check worktree ownership consistency for a branch.

    Args:
        store: SQLite client instance.
        branch: Branch name to check.
        flow_status: Current flow status.
        inactive_flow_statuses: Tuple of inactive flow statuses to skip.

    Returns:
        List of ownership-related issues found.
    """
    if flow_status in inactive_flow_statuses:
        return []  # Skip inactive flows

    from vibe3.services.worktree_ownership_guard import (
        get_current_session_id,
        get_worktree_owner,
    )
    from vibe3.utils.path_helpers import find_worktree_path_for_branch

    try:
        worktree_path = find_worktree_path_for_branch(branch)
        if worktree_path is None:
            return []  # No worktree, skip ownership check

        owner_session = get_worktree_owner(store, str(worktree_path))
        if owner_session is None:
            # Unowned worktree with active flow
            # This could indicate a new flow that hasn't registered ownership yet
            # or a flow created outside of the standard dispatch path
            return [
                f"Worktree for branch '{branch}' has no registered owner session. "
                "This may indicate a flow created outside standard dispatch. "
                "If intentional, no action needed. Otherwise, investigate session "
                "registration."
            ]

        # Check if owner session is still live
        owner_tmux_session = owner_session.get("tmux_session")
        if not owner_tmux_session:
            return []  # Owner session has no tmux_session field (legacy)

        # Check tmux liveness
        from vibe3.agents.backends.async_launcher import has_tmux_session

        if not has_tmux_session(owner_tmux_session):
            # Orphaned ownership: session died but worktree still claimed
            return [
                f"ORPHANED_OWNERSHIP: Worktree for branch '{branch}' is claimed "
                f"by dead session '{owner_tmux_session}'. "
                "Use 'vibe3 task resume --takeover' to take over ownership, "
                "or manually investigate if the session should still be active."
            ]

        # Check if current session matches owner (only if in tmux)
        current_session_id = get_current_session_id()
        if current_session_id and current_session_id != owner_tmux_session:
            # Session mismatch: different session trying to use the worktree
            return [
                f"Session mismatch: Worktree for branch '{branch}' is owned by "
                f"session '{owner_tmux_session}', but current session is "
                f"'{current_session_id}'. "
                "Use 'vibe3 task resume --takeover' to take over if authorized."
            ]

        return []  # Ownership is consistent
    except Exception as exc:
        logger.bind(domain="check", branch=branch).debug(
            f"Could not verify worktree ownership: {exc}"
        )
        return []  # Skip on errors (non-critical check)
