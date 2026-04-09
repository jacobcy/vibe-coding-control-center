"""Event handlers for governance events.

Handlers for governance service and supervisor execution.
"""

import asyncio
import os
from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.governance import (
    DomainEvent,
    GovernanceDecisionRequired,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    SupervisorExecutionCompleted,
)
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.services.orchestra_status_service import OrchestraStatusService


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Handle GovernanceScanStarted event.

    Triggers governance scan execution via GovernanceService and ExecutionCoordinator.
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
    coordinator = ExecutionCoordinator(config, store)

    github = GitHubClient()
    manager = ManagerExecutor(config, dry_run=config.dry_run)
    status_service = OrchestraStatusService(
        config,
        github=github,
        orchestrator=manager.flow_manager,
    )

    # We assign tick count to the service so it can use it for execution name
    governance_service = GovernanceService(
        config,
        status_service=status_service,
        manager=manager,
    )
    governance_service._tick_count = event.tick_count

    async def _do_scan() -> None:
        try:
            prompt, options, task = (
                await governance_service.build_governance_execution_payload()
            )
            if not prompt:
                # e.g. dry-run or circuit breaker
                return

            request = ExecutionRequest(
                role="governance",
                target_branch="governance",
                target_id=1,
                execution_name=governance_service._governance_execution_name(),
                prompt=prompt,
                options=options,
                refs={"task": task},
                env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
                actor="orchestra:governance",
                mode="async",
            )
            result = coordinator.dispatch_execution(request)

            if result.launched:
                logger.bind(
                    domain="governance_handler",
                    tick=event.tick_count,
                ).success("Governance scan dispatched successfully")
            else:
                logger.bind(
                    domain="governance_handler",
                    tick=event.tick_count,
                ).warning(f"Governance scan dispatch failed: {result.reason}")

        except Exception as exc:
            logger.bind(
                domain="governance_handler",
                tick=event.tick_count,
            ).exception(f"Governance scan failed: {exc}")

    try:
        # Called from within heartbeat's async event loop — schedule as task.
        loop = asyncio.get_running_loop()
        loop.create_task(_do_scan(), name=f"governance-scan-tick-{event.tick_count}")
    except RuntimeError:
        # No running loop (e.g. tests, direct CLI call) — safe to use asyncio.run().
        asyncio.run(_do_scan())


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
