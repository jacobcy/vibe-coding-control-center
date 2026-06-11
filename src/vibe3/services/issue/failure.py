"""Issue failure and block side effects service.

This module handles failure/block transitions for issues when
executor or manager runs fail or make no progress.

Intra-subpackage dependency: failure → flow (one-directional; do not reverse).
"""

from __future__ import annotations

from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.services import FlowService, FlowTimelineService
from vibe3.services.issue.flow import IssueFlowService

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
        action: "fail" for runtime failures (writes flow_failed timeline event
            only; error_log is recorded upstream by the caller, e.g.,
            codeagent_runner via ErrorTrackingService.record_error),
            "block" for business blocks (blocked_reason + label).
    """
    role = _ROLE_MAP.get(role, role)
    actor = actor or _ROLE_DEFAULT_ACTOR.get(role, f"agent:{role}")

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

    if not branch or not store:
        return

    if action == "fail":
        timeline = FlowTimelineService(store=store)
        # Dispatcher error: record to SQLite only, do NOT write GitHub comment
        # Runtime errors are exposed via `vibe3 serve status`, not issue comments
        timeline.record_timeline_event(
            branch=branch,
            event_type="flow_failed",
            actor=actor,
            detail=f"Flow failed (runtime): {reason}",
            # issue_number and repo omitted: prevents GitHub comment write
        )
    else:
        FlowService(store=store).block_flow(
            branch=branch,
            reason=reason,
            actor=actor,
            repo=repo,
            event_type="flow_blocked",
        )


def fail_issue(
    *,
    issue_number: int,
    reason: str,
    role: str,
    actor: str | None = None,
) -> None:
    """Generic fail issue handler.

    Writes a flow_failed timeline event only. The runtime error itself is
    recorded to error_log upstream by the caller (e.g., codeagent_runner via
    ErrorTrackingService.record_error); this handler does NOT write to
    error_log to avoid duplicate entries.
    Does NOT write blocked_reason or change flow_status.
    Runtime errors are handled by ERROR system, not BLOCK system.
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
            logger.bind(
                domain="flow",
                action="block_manager_noop",
                issue_number=issue_number,
                reason=reason,
            ).warning(
                f"No flow found for issue #{issue_number},"
                " cannot block — possible flow creation failure"
            )
            return

        branch = str(flows[0].get("branch") or "").strip()
        if not branch:
            logger.bind(
                domain="flow",
                action="block_manager_noop",
                issue_number=issue_number,
                reason=reason,
            ).warning(
                f"Flow has no branch for issue #{issue_number},"
                " cannot block — possible flow creation failure"
            )
            return

        # Reuse block_flow() - eliminates ALL duplication
        from vibe3.services import FlowService

        FlowService(store=store).block_flow(branch, reason=reason, actor=actor)
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
