"""Shared session naming conventions for runtime roles."""


def build_session_name(
    role: str,
    target_type: str,
    target_id: str,
) -> str:
    """Unified naming rule: vibe3-{role}-{target_type}-{target_id}."""
    return f"vibe3-{role}-{target_type}-{target_id}"


def get_manager_session_name(issue_number: int) -> str:
    """Return canonical tmux session name for manager execution."""
    return f"vibe3-manager-issue-{issue_number}"
