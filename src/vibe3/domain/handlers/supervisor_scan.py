"""Supervisor scan domain event handler.

Subscribes to SupervisorIssueIdentified and dispatches the supervisor apply
agent via CLI self-invocation (internal apply --no-async) to ensure
ErrorTrackingService captures API errors in the sync chain.
"""

from typing import Callable, cast

from loguru import logger

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.models.orchestration import IssueInfo


def handle_supervisor_issue_identified(event: SupervisorIssueIdentified) -> None:
    """Dispatch supervisor apply via CLI self-invocation."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.execution.coordinator import ExecutionCoordinator
    from vibe3.execution.issue_role_support import build_issue_async_cli_request
    from vibe3.orchestra.logging import append_orchestra_event
    from vibe3.roles.supervisor import SUPERVISOR_APPLY_ROLE

    config = load_orchestra_config()
    if config.dry_run:
        logger.bind(
            domain="supervisor_handler",
            issue_number=event.issue_number,
        ).info("Dry run: skipping supervisor apply dispatch")
        return

    append_orchestra_event(
        "supervisor",
        f"dispatch-intent #{event.issue_number} (supervisor)",
    )

    # Build minimal IssueInfo from event (title only, no labels needed)
    issue = IssueInfo(
        number=event.issue_number,
        title=event.issue_title or f"Issue {event.issue_number}",
        labels=[],
    )

    # Build CLI self-invocation request (cmd field, no prompt)
    # This ensures the tmux wrapper calls 'internal apply --no-async'
    # which enters CodeagentExecutionService sync chain with ErrorTrackingService
    request = build_issue_async_cli_request(
        role="supervisor",
        issue=issue,
        target_branch=f"issue-{event.issue_number}",
        command_args=["internal", "apply", str(event.issue_number), "--no-async"],
        actor="orchestra:supervisor",
        execution_name=f"vibe3-supervisor-issue-{event.issue_number}",
        refs={"issue_title": event.issue_title or ""},
        worktree_requirement=SUPERVISOR_APPLY_ROLE.worktree,
    )

    store = SQLiteClient()
    coordinator = ExecutionCoordinator(config, store)

    try:
        result = coordinator.dispatch_execution(request)
    except Exception as exc:
        logger.bind(
            domain="supervisor_handler",
            issue_number=event.issue_number,
        ).exception(f"Supervisor apply dispatch failed: {exc}")
        return

    if result and result.launched:
        append_orchestra_event(
            "supervisor",
            f"dispatched #{event.issue_number} " f"session={result.tmux_session}",
        )
    elif result:
        append_orchestra_event(
            "supervisor",
            f"supervisor dispatch skipped: issue=#{event.issue_number} "
            f"reason={result.reason}",
        )


def register_supervisor_scan_handlers() -> None:
    """Register supervisor scan event handlers."""
    from vibe3.domain.publisher import subscribe

    subscribe(
        "SupervisorIssueIdentified",
        cast(Callable[[DomainEvent], None], handle_supervisor_issue_identified),
    )
    logger.bind(domain="events").info("Supervisor scan event handlers registered")
