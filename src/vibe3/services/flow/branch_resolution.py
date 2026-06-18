"""Convenience wrappers for branch resolution that auto-create FlowService.

These wrappers delegate to the shared helper while providing the convenience
of automatic FlowService construction for command-line usage.
"""


def resolve_branch_arg(
    branch_arg: str | None,
) -> str:
    """Resolve --branch argument to a canonical branch name.

    Convenience wrapper that creates FlowService automatically.
    Delegates to shared.resolve_branch_arg with explicit flow_service.

    Rules:
    - None → current git branch
    - digits only → canonical task branch (task/issue-N) if no flow exists
    - otherwise → return as-is (explicit branch name)

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Resolved branch name
    """
    from vibe3.services.flow import FlowService
    from vibe3.services.shared.branches import resolve_branch_arg as _resolve

    flow_service = FlowService()
    return _resolve(branch_arg, flow_service=flow_service)


def resolve_branch_and_issue(
    branch_arg: str | None,
) -> tuple[str, int | None]:
    """Resolve --branch argument and extract issue number in one call.

    Convenience wrapper that creates FlowService automatically.
    Delegates to shared.resolve_branch_and_issue with explicit flow_service.

    Args:
        branch_arg: Branch argument from CLI (may be None, digits, or branch name)

    Returns:
        Tuple of (resolved_branch_name, issue_number or None)
    """
    from vibe3.services.flow import FlowService
    from vibe3.services.shared.branches import (
        resolve_branch_and_issue as _resolve,
    )

    flow_service = FlowService()
    return _resolve(branch_arg, flow_service=flow_service)
