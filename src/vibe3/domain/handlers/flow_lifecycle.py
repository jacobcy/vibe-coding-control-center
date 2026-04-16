"""Event handlers for flow lifecycle events.

Handlers for agent execution events (planner, executor, reviewer).
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
from vibe3.execution.authoritative_ref_gate import require_authoritative_ref
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    block_executor_noop_issue,
    block_planner_noop_issue,
    block_reviewer_noop_issue,
    fail_executor_issue,
)
from vibe3.services.label_service import LabelService


def _handle_completion_with_ref_gate(
    event_name: str,
    issue_number: int,
    branch: str,
    ref_name: str,
    reason: str,
    actor: str,
    block_issue_func: Callable[..., None],  # Accept callable with keyword args
) -> bool:
    """Helper function to handle completion events with authoritative ref gate.

    Args:
        event_name: Event name for logging
        issue_number: Issue number
        branch: Branch name
        ref_name: Reference name to validate (plan_ref, report_ref, audit_ref)
        reason: Reason message if ref is missing
        actor: Actor name
        block_issue_func: Function to call if ref is missing (accepts keyword args)

    Returns:
        True if ref exists, False if blocked
    """
    flow_service = FlowService()
    has_ref = require_authoritative_ref(
        flow_service=flow_service,
        branch=branch,
        ref_name=ref_name,
        issue_number=issue_number,
        reason=reason,
        actor=actor,
        block_issue=block_issue_func,
    )

    if has_ref:
        logger.bind(
            domain="events",
            event=event_name,
            issue=issue_number,
        ).info(f"{ref_name} found, transitioning to handoff")
        LabelService().confirm_issue_state(
            issue_number,
            IssueState.HANDOFF,
            actor=actor,
        )
    else:
        logger.bind(
            domain="events",
            event=event_name,
            issue=issue_number,
        ).warning(f"{ref_name} missing, issue blocked")

    return has_ref


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


def handle_issue_failed(event: IssueFailed) -> None:
    """Handle IssueFailed event.

    Marks the issue as failed via IssueFailureService.
    """
    logger.bind(
        domain="events",
        event="issue_failed",
        issue=event.issue_number,
        reason=event.reason,
    ).info("Handling IssueFailed")

    fail_executor_issue(
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
    )


def handle_issue_blocked(event: IssueBlocked) -> None:
    """Handle IssueBlocked event.

    Blocks the issue via IssueFailureService.
    """
    logger.bind(
        domain="events",
        event="issue_blocked",
        issue=event.issue_number,
        reason=event.reason,
    ).info("Handling IssueBlocked")

    block_executor_noop_issue(
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
    )


def handle_report_ref_required(event: ReportRefRequired) -> None:
    """Handle ReportRefRequired event.

    Validates report reference via AuthoritativeRefGate.
    """
    logger.bind(
        domain="events",
        event="report_ref_required",
        issue=event.issue_number,
        branch=event.branch,
        ref=event.ref_name,
    ).info("Handling ReportRefRequired")

    # Note: This handler validates but doesn't raise exceptions
    # The caller should check the return value if needed
    flow_service = FlowService()
    require_authoritative_ref(
        flow_service=flow_service,
        branch=event.branch,
        ref_name=event.ref_name,
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
        block_issue=block_executor_noop_issue,
    )


def handle_plan_completed(event: PlanCompleted) -> None:
    """Handle PlanCompleted event.

    Validates plan_ref and transitions issue to handoff state.
    """
    logger.bind(
        domain="events",
        event="plan_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Handling PlanCompleted")

    _handle_completion_with_ref_gate(
        event_name="plan_completed",
        issue_number=event.issue_number,
        branch=event.branch,
        ref_name="plan_ref",
        reason="Missing authoritative plan_ref",
        actor=event.actor,
        block_issue_func=block_planner_noop_issue,
    )


def handle_review_completed(event: ReviewCompleted) -> None:
    """Handle ReviewCompleted event.

    Validates audit_ref and transitions issue to handoff state.
    """
    logger.bind(
        domain="events",
        event="review_completed",
        issue=event.issue_number,
        branch=event.branch,
        verdict=event.verdict,
    ).info("Handling ReviewCompleted")

    _handle_completion_with_ref_gate(
        event_name="review_completed",
        issue_number=event.issue_number,
        branch=event.branch,
        ref_name="audit_ref",
        reason=(
            "review output was saved, but no authoritative audit_ref "
            "was registered. Write or regenerate a canonical audit "
            "note and run handoff audit."
        ),
        actor=event.actor,
        block_issue_func=block_reviewer_noop_issue,
    )


def handle_execution_completed(event: ExecutionCompleted) -> None:
    """Handle ExecutionCompleted event.

    Validates report_ref and transitions issue to handoff state.
    """
    logger.bind(
        domain="events",
        event="execution_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Handling ExecutionCompleted")

    _handle_completion_with_ref_gate(
        event_name="execution_completed",
        issue_number=event.issue_number,
        branch=event.branch,
        ref_name="report_ref",
        reason=(
            "executor output was saved, but no authoritative report_ref "
            "was registered. Write a canonical report document and run handoff report."
        ),
        actor=event.actor,
        block_issue_func=block_executor_noop_issue,
    )


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
