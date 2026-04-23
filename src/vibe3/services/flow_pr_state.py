"""Unified PR state evaluation for flow completion decisions."""

from dataclasses import dataclass

from vibe3.models.pr import PRResponse, PRState


@dataclass(frozen=True)
class FlowPRStateResult:
    """Structured PR state evaluation result."""

    pr_found: bool
    pr_number: int | None
    is_merged: bool
    is_closed_not_merged: bool
    can_mark_flow_done: bool


def evaluate_flow_pr_state(pr: PRResponse | None) -> FlowPRStateResult:
    """Evaluate PR state to determine if flow can be marked done.

    This is the single source of truth for PR state evaluation in vibe3.
    Used by check_service._check_branch() and
    flow_dispatch._rebuild_stale_canonical_flow().
    """
    if pr is None:
        return FlowPRStateResult(
            pr_found=False,
            pr_number=None,
            is_merged=False,
            is_closed_not_merged=False,
            can_mark_flow_done=False,
        )

    pr_number = pr.number

    is_merged = pr.state == PRState.MERGED or pr.merged_at is not None

    is_closed_not_merged = pr.state == PRState.CLOSED and pr.merged_at is None

    can_mark_flow_done = is_merged

    return FlowPRStateResult(
        pr_found=True,
        pr_number=pr_number,
        is_merged=is_merged,
        is_closed_not_merged=is_closed_not_merged,
        can_mark_flow_done=can_mark_flow_done,
    )
