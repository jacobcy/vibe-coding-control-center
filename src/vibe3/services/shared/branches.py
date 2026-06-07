"""Branch argument resolution for CLI commands.

Thin wrapper around resolve_command_branch for backward compatibility.
"""

from typing import TYPE_CHECKING

from vibe3.services.pr.resolver import resolve_command_branch

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService


def resolve_branch_arg(
    branch_arg: str | None,
    flow_service: "FlowService | None" = None,
) -> str:
    """Resolve --branch argument to a canonical branch name.

    This is a thin wrapper around resolve_command_branch for backward
    compatibility with existing command imports.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N) if no flow exists
    - otherwise → return as-is (explicit branch name)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)
        flow_service: Optional FlowService instance (for testing). If None, creates
                     a new instance via public API.

    Returns:
        Resolved branch name
    """
    if flow_service is None:
        # Use public API for cross-module import (allows test patching)
        from vibe3.services import FlowService

        flow_service = FlowService()

    return resolve_command_branch(
        position_arg=branch_arg,
        flow_service=flow_service,
        allow_no_flow=False,
        canonical_fallback=True,
    )


def resolve_branch_and_issue(
    branch_arg: str | None,
    flow_service: "FlowService | None" = None,
) -> tuple[str, int | None]:
    """Resolve --branch argument and extract issue number in one call.

    This centralizes the ConventionResolver call to a single invocation,
    eliminating redundant resolver calls in callers that need both branch
    and issue number.

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)
        flow_service: Optional FlowService instance (for testing). If None, creates
                     a new instance via public API.

    Returns:
        Tuple of (resolved_branch_name, issue_number or None)
    """
    # Import through public API for test patch compatibility
    # (cross-module import allows patching "vibe3.services.resolve_branch_arg")
    from vibe3.config.convention_resolver import get_convention
    from vibe3.services import resolve_branch_arg as resolve_via_public_api

    branch = resolve_via_public_api(branch_arg, flow_service=flow_service)
    convention = get_convention().branch
    issue_number = convention.parse_issue_number(branch)
    return branch, issue_number
