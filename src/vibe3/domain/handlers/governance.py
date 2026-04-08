"""Event handlers for governance events.

Handlers for governance service and supervisor execution.
"""

from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.domain.events.governance import (
    DomainEvent,
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    SupervisorExecutionCompleted,
)


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Handle GovernanceScanStarted event.

    Logs the start of a governance scan.
    """
    logger.bind(
        domain="events",
        event="governance_scan_started",
        tick=event.tick_count,
    ).info("Governance scan started")


def handle_governance_scan_completed(event: GovernanceScanCompleted) -> None:
    """Handle GovernanceScanCompleted event.

    Logs the completion of a governance scan with summary stats.
    """
    logger.bind(
        domain="events",
        event="governance_scan_completed",
        tick=event.tick_count,
        active_flows=event.active_flows,
        suggested_issues=event.suggested_issues,
    ).info("Governance scan completed")


def handle_governance_decision_required(event: GovernanceDecisionRequired) -> None:
    """Handle GovernanceDecisionRequired event.

    Adds a comment to the issue requesting manual decision.
    """
    logger.bind(
        domain="events",
        event="governance_decision_required",
        issue=event.issue_number,
        reason=event.reason,
    ).warning("Governance decision required")

    # Add a comment to the issue
    comment_body = (
        f"## ⚠️ Governance Decision Required\n\n" f"**Reason**: {event.reason}\n\n"
    )
    if event.suggested_action:
        comment_body += f"**Suggested Action**: {event.suggested_action}\n\n"

    GitHubClient().add_comment(
        event.issue_number,
        comment_body,
    )


def handle_supervisor_execution_completed(event: SupervisorExecutionCompleted) -> None:
    """Handle SupervisorExecutionCompleted event.

    Logs supervisor execution result and adds comment to issue if needed.
    """
    logger.bind(
        domain="events",
        event="supervisor_execution_completed",
        supervisor_file=event.supervisor_file,
        issue=event.issue_number,
        success=event.success,
    ).info("Supervisor execution completed")

    # If supervisor execution failed on an issue, add a comment
    if not event.success and event.issue_number is not None:
        from vibe3.clients.github_client import GitHubClient

        GitHubClient().add_comment(
            event.issue_number,
            f"❌ Supervisor execution failed for `{event.supervisor_file}`\n\n"
            f"Please check the supervisor logs for details.",
        )


def register_governance_handlers() -> None:
    """Register all governance event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "GovernanceScanStarted",
        cast(Callable[[DomainEvent], None], handle_governance_scan_started),
    )
    subscribe(
        "GovernanceScanCompleted",
        cast(Callable[[DomainEvent], None], handle_governance_scan_completed),
    )
    subscribe(
        "GovernanceDecisionRequired",
        cast(Callable[[DomainEvent], None], handle_governance_decision_required),
    )
    subscribe(
        "SupervisorExecutionCompleted",
        cast(Callable[[DomainEvent], None], handle_supervisor_execution_completed),
    )

    logger.bind(domain="events").info("Governance event handlers registered")
