"""Branch argument resolution for CLI commands.

Reuses issue_branch_resolver for numeric resolution with flow lookup,
adds current-branch fallback for None input.
"""

from vibe3.clients.git_client import GitClient
from vibe3.services.flow_service import FlowService
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


def resolve_branch_arg(branch_arg: str | None) -> str:
    """Resolve --branch argument to a canonical branch name.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N)
    - otherwise → return as-is (explicit branch name)

    Unlike resolve_issue_branch_input:
    - Returns current branch for None (not None)
    - Falls back to canonical name if no flow exists (not original digits)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Resolved branch name
    """
    if branch_arg is None:
        return GitClient().get_current_branch()

    # Delegate to existing resolver (checks flow store for task/dev patterns)
    resolved = resolve_issue_branch_input(branch_arg, FlowService())
    if resolved is None:
        return GitClient().get_current_branch()

    # If resolver returned original digits (no flow), convert to canonical
    if resolved.isdigit():
        return f"task/issue-{resolved}"

    return resolved
