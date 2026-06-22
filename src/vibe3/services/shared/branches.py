"""Branch argument resolution for CLI commands.

Thin wrapper around resolve_command_branch for backward compatibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.services.protocols import FlowQueryProtocol


def _resolve_branch_arg(
    branch_arg: str | None,
    flow_service: "FlowQueryProtocol",
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
        flow_service: FlowService instance implementing FlowQueryProtocol

    Returns:
        Resolved branch name
    """
    import importlib

    if flow_service is None:
        raise ValueError(
            "flow_service is required. "
            "Pass a FlowService instance (from vibe3.services.flow)."
        )

    _pr_resolver = importlib.import_module("vibe3.services.pr.resolver")
    resolve_command_branch = _pr_resolver.resolve_command_branch

    return resolve_command_branch(  # type: ignore[no-any-return]
        position_arg=branch_arg,
        flow_service=flow_service,
        allow_no_flow=False,
        canonical_fallback=True,
    )


def resolve_branch_and_issue(
    branch_arg: str | None,
    flow_service: "FlowQueryProtocol",
) -> tuple[str, int | None]:
    """Resolve --branch argument and extract issue number in one call.

    This centralizes the ConventionResolver call to a single invocation,
    eliminating redundant resolver calls in callers that need both branch
    and issue number.

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)
        flow_service: FlowService instance implementing FlowQueryProtocol

    Returns:
        Tuple of (resolved_branch_name, issue_number or None)
    """
    from vibe3.config import get_convention

    branch = _resolve_branch_arg(branch_arg, flow_service=flow_service)
    convention = get_convention().branch
    issue_number = convention.parse_issue_number(branch)
    return branch, issue_number
