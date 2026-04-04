"""Shared session naming conventions for manager execution."""

from typing import Literal


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


def get_trigger_session_prefix(
    trigger_name: Literal["manager", "plan", "run", "review"],
    issue_number: int,
) -> str:
    """Return session prefix for runtime trigger dispatch detection.

    Args:
        trigger_name: The trigger type (manager, plan, run, review)
        issue_number: The GitHub issue number

    Returns:
        Session prefix for tmux list matching: vibe3-{trigger_name}-issue-{issue_number}
    """
    return f"vibe3-{trigger_name}-issue-{issue_number}"
