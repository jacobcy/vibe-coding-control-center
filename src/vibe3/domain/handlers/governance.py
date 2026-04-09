"""Event handlers for governance events.

Handlers for governance service and supervisor execution.
"""

from typing import Callable

from loguru import logger

from vibe3.agents.execution_lifecycle import ExecutionLifecycleService
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.governance import (
    DomainEvent,
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    SupervisorExecutionCompleted,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.services.capacity_service import CapacityService


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Handle GovernanceScanStarted event.

    Triggers governance scan execution via GovernanceService.
    Uses unified infrastructure services for lifecycle and capacity.
    """
    logger.bind(
        domain="events",
        event="governance_scan_started",
        tick=event.tick_count,
    ).info("Governance scan started")

    # Initialize unified infrastructure services
    config = OrchestraConfig.from_settings()
    store = SQLiteClient()

    # Setup ExecutionLifecycleService for lifecycle recording
    lifecycle = ExecutionLifecycleService(store)

    # Setup CapacityService for capacity control
    from vibe3.agents.backends.codeagent import CodeagentBackend

    backend = CodeagentBackend()
    capacity = CapacityService(config, store, backend)

    # Check capacity before dispatching
    if not capacity.can_dispatch(role="governance", target_id=1):
        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
        ).info("Governance capacity full, skipping scan")
        return

    # Mark in-flight
    capacity.mark_in_flight(role="governance", target_id=1)

    # Record execution started
    lifecycle.record_started(
        role="governance",
        target="governance_scan",
        actor="orchestra:governance",
        refs={},
    )

    logger.bind(
        domain="governance_handler",
        tick=event.tick_count,
    ).debug("Governance handler dispatching scan via GovernanceService")

    # Dispatch governance scan
    try:
        # Initialize dependencies for GovernanceService
        from vibe3.manager.manager_executor import ManagerExecutor
        from vibe3.services.orchestra_status_service import OrchestraStatusService

        github = GitHubClient()
        manager = ManagerExecutor(config, dry_run=config.dry_run)
        status_service = OrchestraStatusService(
            config,
            github=github,
            orchestrator=manager.flow_manager,
        )

        governance_service = GovernanceService(
            config,
            status_service=status_service,
            manager=manager,
        )

        # Run async scan in new event loop (avoids deprecation warning)
        import asyncio

        asyncio.run(governance_service.run_scan())

        # Record completion
        lifecycle.record_completed(
            role="governance",
            target="governance_scan",
            actor="orchestra:governance",
            detail=f"Governance scan completed for tick {event.tick_count}",
            refs={},
        )

        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
        ).success("Governance scan completed successfully")

    except Exception as exc:
        # Record failure
        lifecycle.record_failed(
            role="governance",
            target="governance_scan",
            actor="orchestra:governance",
            error=str(exc),
            refs={},
        )

        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
        ).exception(f"Governance scan failed: {exc}")

        raise

    finally:
        # Clear in-flight marker
        capacity.prune_in_flight(role="governance", target_ids={1})


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
