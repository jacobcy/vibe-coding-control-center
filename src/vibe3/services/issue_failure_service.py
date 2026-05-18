"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.
"""

from __future__ import annotations

from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_timeline_service import FlowTimelineService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService

_ISSUE_FLOW_SERVICE_CACHE: IssueFlowService | None = None


def _get_issue_flow_service() -> IssueFlowService:
    """Return cached IssueFlowService instance."""
    global _ISSUE_FLOW_SERVICE_CACHE
    if _ISSUE_FLOW_SERVICE_CACHE is None:
        _ISSUE_FLOW_SERVICE_CACHE = IssueFlowService()
    return _ISSUE_FLOW_SERVICE_CACHE


_ROLE_DEFAULT_ACTOR = {
    "review": "agent:review",
    "plan": "agent:plan",
    "run": "agent:run",
    "manager": "agent:manager",
}

_ROLE_MAP = {
    "executor": "run",
    "reviewer": "review",
    "planner": "plan",
}


def mark_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
    repo: str | None = None,
    is_noop: bool = False,
    action: Literal["fail", "block"] = "block",
) -> None:
    """Unified issue state marking interface.

    Args:
        action: "fail" for failure events, "block" for block events.
            Determines comment style and deduplication strategy.
    """
    # Normalize role names
    role = _ROLE_MAP.get(role, role)
    actor = actor or _ROLE_DEFAULT_ACTOR.get(role, f"agent:{role}")

    # Get branch from flow state (required for FlowTimelineService)
    branch: str | None = None
    store: SQLiteClient | None = None
    try:
        issue_flow_service = _get_issue_flow_service()
        store = issue_flow_service.store

        flows = store.get_flows_by_issue(issue_number, role="task")
        if flows:
            branch = str(flows[0].get("branch") or "").strip()
    except Exception as e:
        logger.bind(
            domain="flow",
            action="mark_issue",
            issue_number=issue_number,
            error=str(e),
        ).warning(f"Failed to get branch for issue #{issue_number}")

    # Use standard FlowService.block_flow() method
    if branch and store:
        try:
            from vibe3.services.flow_service import FlowService

            FlowService(store=store).block_flow(
                branch=branch,
                reason=reason,
                actor=actor,
                repo=repo,
                event_type="flow_failed" if action == "fail" else "flow_blocked",
            )
        except Exception as e:
            logger.bind(
                domain="flow",
                action="mark_issue",
                issue_number=issue_number,
                error=str(e),
            ).warning(f"Failed to block flow for issue #{issue_number}")


def fail_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
) -> None:
    """Generic fail issue handler.

    Note: This now sets state/blocked instead of state/failed.
    The failed state is deprecated - all errors are now modeled as blocked
    with structured blocked_reason field.

    IssueFailed event is still recorded for observability.
    blocked_reason is recorded in flow state directly in mark_issue().
    """
    mark_issue(
        issue_number=issue_number,
        reason=reason,
        role=role,
        actor=actor,
        action="fail",
    )


def block_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
    repo: str | None = None,
    is_noop: bool = False,
) -> None:
    """Generic block issue handler."""
    mark_issue(
        issue_number=issue_number,
        reason=reason,
        role=role,
        actor=actor,
        repo=repo,
        is_noop=is_noop,
        action="block",
    )


def resume_issue(
    *,
    issue_number: int,
    reason: str,
    from_state: str = "blocked",  # Unified: only "blocked" now
    to_state: IssueState = IssueState.READY,
    repo: str | None = None,
    actor: str = "human:resume",
) -> None:
    """Generic resume issue handler.

    Args:
        issue_number: GitHub issue number
        reason: Resume reason for comment
        from_state: Previous state (now always "blocked")
        to_state: Target state (default: READY)
        repo: Optional repository
        actor: Actor name for events
    """
    # Write to flow (source of truth) before GitHub sync
    branch: str | None = None
    store: SQLiteClient | None = None
    try:
        issue_flow_service = _get_issue_flow_service()
        store = issue_flow_service.store
        flows = issue_flow_service.store.get_flows_by_issue(issue_number, role="task")
        if flows:
            branch = str(flows[0].get("branch") or "").strip()
    except Exception as e:
        logger.bind(
            domain="flow",
            action="resume_issue",
            issue_number=issue_number,
            error=str(e),
        ).warning(f"Flow event recording failed for issue #{issue_number}")

    # Add [flow] timeline comment via FlowTimelineService
    if branch and store:
        try:
            timeline_service = FlowTimelineService(store=store)
            timeline_service.record_timeline_event(
                branch=branch,
                event_type="resumed",
                actor=actor,
                detail=f"Resumed from {from_state} to {to_state.value}: {reason}",
                issue_number=issue_number,
                repo=repo,
            )
        except Exception as e:
            logger.bind(
                domain="flow",
                action="resume_issue",
                issue_number=issue_number,
                error=str(e),
            ).warning(f"Timeline comment failed for issue #{issue_number}")

    # Transition issue state via LabelService
    LabelService(repo=repo).confirm_issue_state(
        issue_number,
        to_state,
        actor=actor,
        force=True,
    )


# Role-specific convenience wrappers for fail_issue/block_issue
def fail_reviewer_issue(
    *, issue_number: int, reason: str, actor: str = "agent:review"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="review", actor=actor)


def fail_planner_issue(
    *, issue_number: int, reason: str, actor: str = "agent:plan"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="plan", actor=actor)


def fail_executor_issue(*, issue_number: int, reason: str, actor: str) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="run", actor=actor)


def fail_manager_issue(
    *, issue_number: int, reason: str, actor: str = "agent:manager"
) -> None:
    fail_issue(issue_number=issue_number, reason=reason, role="manager", actor=actor)


def block_manager_noop_issue(
    *, issue_number: int, repo: str | None, reason: str, actor: str
) -> None:
    """Block issue via unified block_flow logic.

    Refactored to reuse FlowService.block_flow() for consistency.
    All operations (write blocked_reason, transition label, add comment, add event)
    are handled by block_flow() - no duplication needed.
    """
    try:
        issue_flow_service = _get_issue_flow_service()
        store = issue_flow_service.store

        # Find any flow for this issue
        flows = store.get_flows_by_issue(issue_number, role="task")
        if not flows:
            return

        branch = str(flows[0].get("branch") or "").strip()
        if not branch:
            return

        # Reuse block_flow() - eliminates ALL duplication
        from vibe3.services import flow_service

        flow_service.FlowService(store=store).block_flow(
            branch, reason=reason, actor=actor
        )
        # No separate event needed - block_flow() already adds flow_blocked event

    except Exception as e:
        logger.bind(
            domain="flow",
            action="block_manager_noop",
            issue_number=issue_number,
            error=str(e),
        ).warning(f"Failed to block issue #{issue_number}")


def block_planner_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:plan",
    repo: str | None = None,
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="plan",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def block_executor_noop_issue(
    *, issue_number: int, reason: str, actor: str = "agent:run", repo: str | None = None
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="run",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def block_reviewer_noop_issue(
    *,
    issue_number: int,
    reason: str,
    actor: str = "agent:review",
    repo: str | None = None,
) -> None:
    block_issue(
        issue_number=issue_number,
        reason=reason,
        role="review",
        actor=actor,
        repo=repo,
        is_noop=True,
    )


def resume_blocked_issue_to_ready(
    *, issue_number: int, repo: str | None, reason: str, actor: str = "human:resume"
) -> None:
    resume_issue(
        issue_number=issue_number,
        reason=reason,
        from_state="blocked",
        repo=repo,
        actor=actor,
    )
