"""Branch argument resolution for CLI commands.

Thin wrapper around resolve_command_branch for backward compatibility.
"""

from vibe3.services.flow_service import FlowService
from vibe3.services.pr.resolver import resolve_command_branch


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


def resolve_branch_and_issue(branch_arg: str | None) -> tuple[str, int | None]:
    """Resolve --branch argument and extract issue number in one call.

    This centralizes the ConventionResolver call to a single invocation,
    eliminating redundant resolver calls in callers that need both branch
    and issue number.

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Tuple of (resolved_branch_name, issue_number or None)
    """
    # Lazy imports to allow test patching via bridge file
    from vibe3.config.convention_resolver import get_convention

    branch = resolve_branch_arg(branch_arg)
    convention = get_convention().branch
    issue_number = convention.parse_issue_number(branch)
    return branch, issue_number
