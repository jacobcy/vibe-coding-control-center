"""Flow create decision helper."""

from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.flow import CreateDecision
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF


def decide_create_from_current_worktree(
    store: Any,
    current_branch: str,
) -> CreateDecision:
    """Determine if a new flow can be created in the current worktree."""
    flow_data = store.get_flow_state(current_branch)

    if not flow_data:
        return CreateDecision(
            allowed=True,
            reason="No active flow in current worktree",
            start_ref=MAIN_BRANCH_REF,
            requires_new_worktree=False,
        )

    status = flow_data.get("flow_status", "active")

    # Fetch real-time PR readiness from GitHub
    gh = GitHubClient()
    is_waiting_review = False
    pr_number = flow_data.get("pr_number")
    try:
        pr = gh.get_pr(pr_number, current_branch)
        if pr:
            is_waiting_review = pr.is_ready
    except Exception as e:
        logger.bind(domain="flow", branch=current_branch).warning(
            f"Failed to check PR readiness for decision: {e}"
        )
        # Fallback to local cache if offline/error
        is_waiting_review = bool(flow_data.get("pr_ready_for_review"))

    if status == "active" and is_waiting_review:
        return CreateDecision(
            allowed=True,
            reason=(
                "Current flow PR is ready and waiting review - "
                "safe to start a new target"
            ),
            start_ref=MAIN_BRANCH_REF,
            requires_new_worktree=False,
        )

    if status == "active":
        return CreateDecision(
            allowed=False,
            reason="Current flow is active - cannot create new flow in same worktree",
            requires_new_worktree=True,
            guidance=(
                "Use 'vibe3 wtnew <name>' to create a new worktree for new " "features"
            ),
        )

    if status == "blocked":
        return CreateDecision(
            allowed=True,
            reason=(
                "Current flow is blocked - can create downstream flow from "
                "current branch"
            ),
            start_ref=current_branch,
            allow_base_current=True,
            requires_new_worktree=False,
        )

    if status in ("done", "aborted", "stale"):
        return CreateDecision(
            allowed=True,
            reason=f"Current flow is {status} - safe to start new target",
            start_ref=MAIN_BRANCH_REF,
            requires_new_worktree=False,
        )

    return CreateDecision(
        allowed=True,
        reason="Unknown status - allowing with caution",
        start_ref=MAIN_BRANCH_REF,
        requires_new_worktree=False,
    )
