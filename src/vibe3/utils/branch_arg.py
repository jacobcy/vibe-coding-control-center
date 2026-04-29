"""Branch argument resolution for CLI commands."""

from vibe3.clients.git_client import GitClient
from vibe3.services.issue_flow_service import IssueFlowService


def resolve_branch_arg(branch_arg: str | None) -> str:
    """Resolve --branch argument to a canonical branch name.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N)
    - otherwise → return as-is (explicit branch name)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Resolved branch name
    """
    if branch_arg is None:
        return GitClient().get_current_branch()

    stripped = branch_arg.strip()
    if stripped.isdigit():
        return IssueFlowService().canonical_branch_name(int(stripped))
    return stripped
