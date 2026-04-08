"""Event handlers for flow lifecycle events.

Handlers for agent execution events (planner, executor, reviewer).
"""

from typing import Callable

from loguru import logger

from vibe3.domain.events.flow_lifecycle import (
    DomainEvent,
    IssueBlocked,
    IssueFailed,
    IssueStateChanged,
    PlanCompleted,
    ReportRefRequired,
    ReviewCompleted,
)
from vibe3.models.orchestration import IssueState
from vibe3.services.authoritative_ref_gate import require_authoritative_ref
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    block_executor_noop_issue,
    block_planner_noop_issue,
    block_reviewer_noop_issue,
    confirm_plan_handoff,
    fail_executor_issue,
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

    flow_service = FlowService()
    has_plan_ref = require_authoritative_ref(
        flow_service=flow_service,
        branch=event.branch,
        ref_name="plan_ref",
        issue_number=event.issue_number,
        reason="Missing authoritative plan_ref",
        actor=event.actor,
        block_issue=block_planner_noop_issue,
    )

    if has_plan_ref:
        logger.bind(
            domain="events",
            event="plan_completed",
            issue=event.issue_number,
        ).info("plan_ref found, transitioning to handoff")
        confirm_plan_handoff(
            issue_number=event.issue_number,
            actor=event.actor,
        )
    else:
        logger.bind(
            domain="events",
            event="plan_completed",
            issue=event.issue_number,
        ).warning("plan_ref missing, issue blocked")


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

    flow_service = FlowService()
    has_audit_ref = require_authoritative_ref(
        flow_service=flow_service,
        branch=event.branch,
        ref_name="audit_ref",
        issue_number=event.issue_number,
        reason=(
            "review output was saved, but no authoritative audit_ref "
            "was registered. Write or regenerate a canonical audit "
            "note and run handoff audit."
        ),
        actor=event.actor,
        block_issue=block_reviewer_noop_issue,
    )

    if has_audit_ref:
        logger.bind(
            domain="events",
            event="review_completed",
            issue=event.issue_number,
        ).info("audit_ref found, transitioning to handoff")
        LabelService().confirm_issue_state(
            event.issue_number,
            IssueState.HANDOFF,
            actor=event.actor,
        )
    else:
        logger.bind(
            domain="events",
            event="review_completed",
            issue=event.issue_number,
        ).warning("audit_ref missing, issue blocked")


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
        "ReviewCompleted", cast(Callable[[DomainEvent], None], handle_review_completed)
    )

    logger.bind(domain="events").info("Flow lifecycle event handlers registered")
