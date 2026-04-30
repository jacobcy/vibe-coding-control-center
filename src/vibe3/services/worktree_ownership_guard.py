"""Worktree ownership guard to prevent cross-agent conflicts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.exceptions import UserError

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class WorktreeOwnerMismatchError(UserError):
    """Raised when current session doesn't own the worktree."""

    def __str__(self) -> str:
        return self.message


def get_current_session_id() -> str | None:
    """Return the current tmux session name, or None if outside tmux.

    Uses tmux display-message to get the actual session name (e.g.,
    'vibe3-executor-issue-42') rather than the TMUX env var which is
    a socket path format.

    Returns:
        Session name if in tmux, None otherwise (direct user).
    """
    import subprocess

    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{session_name}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_worktree_owner(
    store: SQLiteClient, worktree_path: str
) -> dict[str, Any] | None:
    """Return the session dict that owns this worktree, or None if unowned.

    Args:
        store: SQLite client instance.
        worktree_path: Absolute path to the worktree directory.

    Returns:
        Session dict if a live owner exists, None otherwise.
    """
    return store.get_worktree_owner_session(worktree_path)


def ensure_worktree_ownership(
    store: SQLiteClient,
    worktree_path: str,
    *,
    allow_takeover: bool = False,
    takeover_reason: str = "",
) -> None:
    """Validate that the current session owns this worktree.

    Guards are NO-OP when:
    - The worktree has no registered owner (first use).
    - Running outside tmux (direct user, TMUX env var absent).
    - The current tmux session matches the recorded owner.

    Args:
        store: SQLite client instance.
        worktree_path: Absolute path to the worktree directory.
        allow_takeover: If True, allow taking over ownership.
        takeover_reason: Reason for takeover (for audit logging).

    Raises:
        WorktreeOwnerMismatchError: When session mismatch and takeover not allowed.
    """
    current_session_id = get_current_session_id()

    # Outside tmux → always authorized (direct user)
    if current_session_id is None:
        return

    # Look up the worktree owner
    owner_session = get_worktree_owner(store, worktree_path)

    # No owner → first use, allow
    if owner_session is None:
        return

    # Extract owner's tmux session identifier
    owner_tmux_session = owner_session.get("tmux_session")
    owner_session_name = owner_session.get("session_name", "unknown")

    # If owner has no tmux_session recorded, treat as unowned
    if not owner_tmux_session:
        return

    # Check if current session matches owner
    if current_session_id == owner_tmux_session:
        return  # Current session owns it

    # Mismatch: current session doesn't own the worktree
    if allow_takeover:
        takeover_worktree(
            store,
            worktree_path,
            current_session_id,
            takeover_reason,
        )
        return

    # Build actionable error message
    current_branch = store.get_flow_state(worktree_path.split("/")[-1])
    branch_hint = ""
    if current_branch:
        branch_name = current_branch.get("branch", "unknown")
        branch_hint = f"\n  Branch: {branch_name}"

    raise WorktreeOwnerMismatchError(
        f"Worktree ownership mismatch detected:\n"
        f"  Worktree: {worktree_path}{branch_hint}\n"
        f"  Current session: {current_session_id}\n"
        f"  Owner session: {owner_tmux_session} ({owner_session_name})\n\n"
        f"This worktree is in use by another session. Options:\n"
        f"  1. Wait for the other session to complete and release the worktree\n"
        f"  2. Use `vibe3 task resume --takeover` to explicitly take over\n"
        f"  3. Switch to a different worktree: `vibe3 task resume <issue>`"
    )


def takeover_worktree(
    store: SQLiteClient,
    worktree_path: str,
    new_owner_id: str,
    reason: str,
) -> None:
    """Log a worktree takeover event and update session binding.

    Args:
        store: SQLite client instance.
        worktree_path: Absolute path to the worktree directory.
        new_owner_id: The tmux session ID taking ownership.
        reason: Reason for takeover (for audit logging).
    """
    from vibe3.services.signature_service import SignatureService

    # Get the branch name from worktree path (last component)
    branch = worktree_path.split("/")[-1]
    actor = SignatureService.get_worktree_actor()

    # Log the takeover event
    store.add_event(
        branch,
        "worktree_takeover",
        actor,
        detail=f"Worktree takeover: {reason}" if reason else "Worktree takeover",
        refs={
            "new_owner_id": new_owner_id,
            "worktree_path": worktree_path,
        },
    )

    # Update the owning session's tmux_session field
    # Find the most recent live session for this worktree and update it
    owner_session = store.get_worktree_owner_session(worktree_path)
    if owner_session:
        session_id = owner_session.get("id")
        if session_id:
            store.update_runtime_session(
                session_id,
                tmux_session=new_owner_id,
            )
