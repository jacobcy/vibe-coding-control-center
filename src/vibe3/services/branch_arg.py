"""Branch argument resolution for CLI commands.

Thin wrapper around resolve_command_branch for backward compatibility.
"""

from vibe3.services.flow_service import FlowService
from vibe3.services.pr_branch_resolver import resolve_command_branch


def resolve_branch_arg(branch_arg: str | None) -> str:
    """Resolve --branch argument to a canonical branch name.

    This is a thin wrapper around resolve_command_branch for backward
    compatibility with existing command imports.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N) if no flow exists
    - otherwise → return as-is (explicit branch name)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Resolved branch name
    """
    return resolve_command_branch(
        position_arg=branch_arg,
        flow_service=FlowService(),
        allow_no_flow=False,
        canonical_fallback=True,
    )
