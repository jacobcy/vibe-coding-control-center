"""Event handlers for governance events.

Handlers for governance service and supervisor execution.
"""

import asyncio
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


async def _run_governance_scan_async(
    governance_service: GovernanceService,
    lifecycle: ExecutionLifecycleService,
    capacity: CapacityService,
    tick_count: int,
) -> None:
    """Run governance scan with unified lifecycle and capacity tracking.

    Designed to be scheduled as an asyncio task from the sync handler,
    so it never blocks the heartbeat event loop.
    """
    try:
        await governance_service.run_scan()

        lifecycle.record_completed(
            role="governance",
            target="governance_scan",
            actor="orchestra:governance",
            detail=f"Governance scan completed for tick {tick_count}",
            refs={},
        )

        logger.bind(
            domain="governance_handler",
            tick=tick_count,
        ).success("Governance scan completed successfully")

    except Exception as exc:
        lifecycle.record_failed(
            role="governance",
            target="governance_scan",
            actor="orchestra:governance",
            error=str(exc),
            refs={},
        )

        logger.bind(
            domain="governance_handler",
            tick=tick_count,
        ).exception(f"Governance scan failed: {exc}")

    finally:
        capacity.prune_in_flight(role="governance", target_ids={1})


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Handle GovernanceScanStarted event.

    Triggers governance scan execution via GovernanceService.
    Uses unified infrastructure services for lifecycle and capacity.

    Schedules the async scan as a task on the running event loop to avoid
    calling asyncio.run() inside an already-running loop (heartbeat context).
    """
    logger.bind(
        domain="events",
        event="governance_scan_started",
        tick=event.tick_count,
    ).info("Governance scan started")

    # Initialize unified infrastructure services
    config = OrchestraConfig.from_settings()
    store = SQLiteClient()
    lifecycle = ExecutionLifecycleService(store)

    from vibe3.agents.backends.codeagent import CodeagentBackend

    backend = CodeagentBackend()
    capacity = CapacityService(config, store, backend)

    # Capacity check (sync, before scheduling any async work)
    if not capacity.can_dispatch(role="governance", target_id=1):
        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
        ).info("Governance capacity full, skipping scan")
        return

    capacity.mark_in_flight(role="governance", target_id=1)

    lifecycle.record_started(
        role="governance",
        target="governance_scan",
        actor="orchestra:governance",
        refs={},
    )

    logger.bind(
        domain="governance_handler",
        tick=event.tick_count,
    ).debug("Governance handler scheduling scan via GovernanceService")

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

    coro = _run_governance_scan_async(
        governance_service, lifecycle, capacity, event.tick_count
    )

    try:
        # Called from within heartbeat's async event loop — schedule as task.
        loop = asyncio.get_running_loop()
        loop.create_task(coro, name=f"governance-scan-tick-{event.tick_count}")
    except RuntimeError:
        # No running loop (e.g. tests, direct CLI call) — safe to use asyncio.run().
        asyncio.run(coro)


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
