"""Shared session naming conventions and utilities for manager execution."""


def build_session_name(
    role: str,
    target_type: str,
    target_id: str,
) -> str:
    """Unified naming rule: vibe3-{role}-{target_type}-{target_id}."""
    return f"vibe3-{role}-{target_type}-{target_id}"


def get_manager_session_name(issue_number: int) -> str:
    """Return the canonical tmux session name for manager execution.

    This naming convention is the single source of truth for:
    - tmux execution name (manager_executor, run.py)
    - async log naming prefix
    - live-session detection prefix (state_label_dispatch)

    Args:
        issue_number: The GitHub issue number being managed

    Returns:
        Canonical session name: vibe3-manager-issue-{issue_number}
    """
    return f"vibe3-manager-issue-{issue_number}"
