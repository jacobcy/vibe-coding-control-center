"""Shared gate for authoritative ref validation across agent phases."""

from __future__ import annotations

from collections.abc import Callable

from vibe3.services.flow_service import FlowService


def has_authoritative_ref(
    *,
    flow_service: FlowService,
    branch: str,
    ref_name: str,
) -> bool:
    """Return whether the current flow has the named authoritative ref."""
    flow = flow_service.get_flow_status(branch)
    if not flow:
        return False
    return bool(getattr(flow, ref_name, None))


def require_authoritative_ref(
    *,
    flow_service: FlowService,
    branch: str,
    ref_name: str,
    issue_number: int | None,
    reason: str,
    actor: str,
    block_issue: Callable[..., None],
    repo: str | None = None,
) -> bool:
    """Ensure the named authoritative ref exists or invoke the block handler.

    Args:
        flow_service: Flow service instance
        branch: Branch name
        ref_name: Name of the authoritative ref
            (e.g., "plan_ref", "report_ref", "audit_ref")
        issue_number: GitHub issue number (optional)
        reason: Reason for blocking if ref is missing
        actor: Actor performing the block
        block_issue: Callback to block the issue
        repo: Repository (owner/repo format, optional)

    Returns:
        True if authoritative ref exists, False otherwise
    """
    if has_authoritative_ref(
        flow_service=flow_service,
        branch=branch,
        ref_name=ref_name,
    ):
        return True

    if issue_number is not None:
        block_issue(
            issue_number=issue_number,
            reason=reason,
            actor=actor,
            repo=repo,
        )
    return False
