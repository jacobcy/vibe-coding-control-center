"""Helpers for resolving issue numbers to canonical flow branches.

This module provides branch resolution logic that is shared across
different service modules (issue, pr, etc.).
"""

from collections.abc import Iterable, Mapping
from typing import Any

from vibe3.config import get_convention
from vibe3.exceptions import UserError


def iter_issue_branch_candidates(issue_number: int) -> Iterable[str]:
    """Yield supported branch candidates for an issue number."""
    convention = get_convention()
    yield convention.branch.canonical_branch(issue_number)
    yield convention.branch.dev_branch(issue_number)


def resolve_issue_branch_input(
    branch: str | None,
    flow_service: Any,
    *,
    allow_no_flow: bool = False,
) -> str | None:
    """Resolve numeric issue input with conflict detection.

    Changes from original:
    - Uses get_flows_by_issue() for bound flows first
    - Conflict detection for multiple active flows
    - Smart warnings for unbound or aborted candidates

    Args:
        branch: User input (branch name or issue number)
        flow_service: FlowService instance
        allow_no_flow: If True, return None instead of raising UserError
            when no flows exist at all (Step 5). All other error paths
            (conflict, all-aborted, unbound-candidates) still raise.

    Returns:
        Resolved branch name, or None if allow_no_flow=True and no flows exist

    Raises:
        UserError: When conflicts or missing flows detected
    """
    # Step 1: Check input type and normalize
    if branch is None:
        return None

    stripped = branch.strip()
    if not stripped.isdigit():
        return stripped

    issue_number = int(stripped)
    store = getattr(flow_service, "store")

    # Step 2: Query flows with issue binding
    candidates = store.get_flows_by_issue(issue_number, role="task")

    if candidates:
        # Step 3: Resolve with conflict detection
        return _resolve_best_flow_from_candidates(candidates, issue_number)

    # Step 4: Check unbound candidates (smart warning)
    unbound_candidates = []
    for candidate in iter_issue_branch_candidates(issue_number):
        state = store.get_flow_state(candidate)
        if isinstance(state, Mapping):
            unbound_candidates.append(state)

    if unbound_candidates:
        # Smart warning: has candidates but no binding
        details = "\n  - ".join(_format_flow_details(f) for f in unbound_candidates)
        raise UserError(
            f"Found flow(s) for issue #{issue_number} "
            f"candidates but without task binding:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow bind {issue_number} --role task' to link the issue."
        )

    # Step 5: No flows at all
    if allow_no_flow:
        return None
    raise UserError(
        f"No flow found for issue #{issue_number}. "
        f"Use '/vibe-new issue {issue_number}' to create a flow.\n"
        f"提示：如果是 PR 号，请使用 --pr {issue_number}"
    )


def _format_flow_details(flow: Mapping[str, Any]) -> str:
    """Format single flow details: branch (status: X, pr: Y).

    Args:
        flow: Flow state dict from database

    Returns:
        Human-readable string like "dev/issue-976 (status: active, pr: #990)"
    """
    branch = flow.get("branch", "unknown")
    status = flow.get("flow_status", "unknown")

    # PR info: check pr_ref or derive from pr_number
    pr_ref = flow.get("pr_ref")
    if isinstance(pr_ref, str) and pr_ref:
        # Extract PR number from URL (e.g., "https://github.com/.../pull/990")
        pr_number = pr_ref.split("/")[-1]
        pr_info = f"pr: #{pr_number}"
    else:
        pr_info = "pr: none"

    return f"{branch} (status: {status}, {pr_info})"


def _resolve_best_flow_from_candidates(
    candidates: list[dict[str, Any]],
    issue_number: int,
) -> str:
    """Select best flow or raise UserError for conflicts.

    Args:
        candidates: List of flow dicts from get_flows_by_issue()
        issue_number: Issue number being resolved
    Returns:
        Selected branch name

    Raises:
        UserError: When multiple active flows conflict or all aborted
    """
    # Priority 1: Non-aborted flows
    non_aborted = [f for f in candidates if f["flow_status"] != "aborted"]

    if len(non_aborted) == 1:
        # Auto-select the only non-aborted flow
        return str(non_aborted[0]["branch"])

    # Priority 2: Check for multiple active flows (conflict)
    active = [f for f in candidates if f["flow_status"] == "active"]

    if len(active) > 1:
        # Conflict: multiple active flows
        details = "\n  - ".join(_format_flow_details(f) for f in active)
        raise UserError(
            f"Multiple active flows detected for issue #{issue_number}:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow abort <branch>' to resolve the conflict."
        )

    # Priority 3: Single active flow among multiple non-aborted
    if len(active) == 1:
        return str(active[0]["branch"])

    # Priority 4: All flows are aborted
    if not non_aborted and candidates:
        details = "\n  - ".join(_format_flow_details(f) for f in candidates)
        raise UserError(
            f"All flows for issue #{issue_number} are aborted:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow restore <branch>' to reactivate a flow."
        )

    # Fallback: Should not reach here if candidates is non-empty
    return str(candidates[0]["branch"])
