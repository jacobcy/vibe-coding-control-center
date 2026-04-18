"""Event handlers for flow lifecycle events.

Handlers for agent execution events (planner, executor, reviewer).

Note: Ref validation (audit_ref, plan_ref, report_ref) is handled by
apply_required_ref_post_sync in the sync runner's post_sync_hook, which
has full before/after snapshot context. Domain event handlers only log
completion events and do NOT perform ref validation — the domain event
path lacks execution context and can fire incorrectly when the agent
never actually ran.
"""

from typing import Callable

from loguru import logger

from vibe3.domain.events.flow_lifecycle import (
    DomainEvent,
    ExecutionCompleted,
    IssueBlocked,
    IssueFailed,
    IssueStateChanged,
    PlanCompleted,
    ReportRefRequired,
    ReviewCompleted,
)
from vibe3.models.orchestration import IssueState
from vibe3.services.issue_failure_service import (
    block_executor_noop_issue,
    block_manager_noop_issue,
    block_planner_noop_issue,
    block_reviewer_noop_issue,
    fail_executor_issue,
    fail_manager_issue,
    fail_planner_issue,
    fail_reviewer_issue,
)
from vibe3.services.label_service import LabelService


def handle_issue_state_changed(event: IssueStateChanged) -> None:
    """Handle IssueStateChanged event.

    Updates the issue's state label via LabelService.
    """
    logger.bind(
        domain="events",
        event="issue_state_changed",
        issue=event.issue_number,
        state=f"{event.from_state} → {event.to_state}",
    ).info("Handling IssueStateChanged")

    to_state = IssueState(event.to_state)
    LabelService().confirm_issue_state(
        event.issue_number,
        to_state,
        actor=event.actor,
    )


_ROLE_FAIL_DISPATCH: dict[str, Callable[..., None]] = {
    "planner": fail_planner_issue,
    "executor": fail_executor_issue,
    "reviewer": fail_reviewer_issue,
    "manager": fail_manager_issue,
}

_ROLE_BLOCK_DISPATCH: dict[str, Callable[..., None]] = {
    "planner": block_planner_noop_issue,
    "executor": block_executor_noop_issue,
    "reviewer": block_reviewer_noop_issue,
    "manager": block_manager_noop_issue,
}


def handle_issue_failed(event: IssueFailed) -> None:
    """Handle IssueFailed event.

    Routes to role-specific failure handler based on event.role field.
    Falls back to executor for backward compatibility.
    """
    role = event.role or "executor"
    logger.bind(
        domain="events",
        event="issue_failed",
        issue=event.issue_number,
        role=role,
        reason=event.reason,
    ).info("Handling IssueFailed")

    fail_func = _ROLE_FAIL_DISPATCH.get(role, fail_executor_issue)
    fail_func(
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
    )


def handle_issue_blocked(event: IssueBlocked) -> None:
    """Handle IssueBlocked event.

    Routes to role-specific block handler based on event.role field.
    Falls back to executor for backward compatibility.
    """
    role = event.role or "executor"
    logger.bind(
        domain="events",
        event="issue_blocked",
        issue=event.issue_number,
        role=role,
        reason=event.reason,
    ).info("Handling IssueBlocked")

    block_func = _ROLE_BLOCK_DISPATCH.get(role, block_executor_noop_issue)
    block_func(
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
        repo=None,
    )


def handle_report_ref_required(event: ReportRefRequired) -> None:
    """Handle ReportRefRequired event.

    Logs completion only. Ref validation is handled by
    apply_required_ref_post_sync in the sync runner's post_sync_hook.
    """
    logger.bind(
        domain="events",
        event="report_ref_required",
        issue=event.issue_number,
        branch=event.branch,
        ref=event.ref_name,
    ).info("Handling ReportRefRequired")


def handle_plan_completed(event: PlanCompleted) -> None:
    """Handle PlanCompleted event.

    Logs completion only. Ref validation is handled by
    apply_required_ref_post_sync in the sync runner's post_sync_hook.
    """
    logger.bind(
        domain="events",
        event="plan_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Handling PlanCompleted")


def handle_review_completed(event: ReviewCompleted) -> None:
    """Handle ReviewCompleted event.

    Logs completion only. Ref validation is handled by
    apply_required_ref_post_sync in the sync runner's post_sync_hook.
    """
    logger.bind(
        domain="events",
        event="review_completed",
        issue=event.issue_number,
        branch=event.branch,
        verdict=event.verdict,
    ).info("Handling ReviewCompleted")


def handle_execution_completed(event: ExecutionCompleted) -> None:
    """Handle ExecutionCompleted event.

    Logs completion only. Ref validation is handled by
    apply_required_ref_post_sync in the sync runner's post_sync_hook.
    """
    logger.bind(
        domain="events",
        event="execution_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Handling ExecutionCompleted")


def register_flow_lifecycle_handlers() -> None:
    """Register all flow lifecycle event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "IssueStateChanged",
        cast(Callable[[DomainEvent], None], handle_issue_state_changed),
    )
    subscribe("IssueFailed", cast(Callable[[DomainEvent], None], handle_issue_failed))
    subscribe("IssueBlocked", cast(Callable[[DomainEvent], None], handle_issue_blocked))
    subscribe(
        "ReportRefRequired",
        cast(Callable[[DomainEvent], None], handle_report_ref_required),
    )
    subscribe(
        "PlanCompleted", cast(Callable[[DomainEvent], None], handle_plan_completed)
    )
    subscribe(
        "ExecutionCompleted",
        cast(Callable[[DomainEvent], None], handle_execution_completed),
    )
    subscribe(
        "ReviewCompleted", cast(Callable[[DomainEvent], None], handle_review_completed)
    )

    logger.bind(domain="events").info("Flow lifecycle event handlers registered")
