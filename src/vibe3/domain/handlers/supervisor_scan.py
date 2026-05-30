"""Supervisor scan domain event handler.

Subscribes to SupervisorIssueIdentified and dispatches the supervisor apply
agent via CLI self-invocation (internal apply --no-async) to ensure
ErrorTrackingService captures API errors in the sync chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import get_store
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.domain.handler_registry import register_handler
from vibe3.models.orchestration import IssueInfo
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected

if TYPE_CHECKING:
    from vibe3.execution.coordinator import ExecutionCoordinator


@register_handler("SupervisorIssueIdentified")
def handle_supervisor_issue_identified(
    event: SupervisorIssueIdentified, /, coordinator: ExecutionCoordinator | None = None
) -> None:
    """Dispatch supervisor apply via CLI self-invocation."""
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

    if coordinator is None:
        from vibe3.execution.coordinator import ExecutionCoordinator

        with get_store() as store:
            coordinator = ExecutionCoordinator(config, store)

            try:
                result = coordinator.dispatch_execution(request)
                record_dispatch_failure_if_unexpected(
                    result=result,
                    role="supervisor",
                    issue_number=event.issue_number,
                    branch=f"issue-{event.issue_number}",
                    dispatch_source="automatic",
                )
            except Exception as exc:
                record_dispatch_failure_if_unexpected(
                    role="supervisor",
                    issue_number=event.issue_number,
                    branch=f"issue-{event.issue_number}",
                    exception=exc,
                    dispatch_source="automatic",
                )
                logger.bind(
                    domain="supervisor_handler",
                    issue_number=event.issue_number,
                ).exception(f"Supervisor apply dispatch failed: {exc}")
                return
    else:
        try:
            result = coordinator.dispatch_execution(request)
            record_dispatch_failure_if_unexpected(
                result=result,
                role="supervisor",
                issue_number=event.issue_number,
                branch=f"issue-{event.issue_number}",
                dispatch_source="automatic",
            )
        except Exception as exc:
            record_dispatch_failure_if_unexpected(
                role="supervisor",
                issue_number=event.issue_number,
                branch=f"issue-{event.issue_number}",
                exception=exc,
                dispatch_source="automatic",
            )
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
