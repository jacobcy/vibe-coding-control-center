"""Event handlers for supervisor apply events.

Handlers for L2 supervisor handoff service execution chain.

This chain handles lightweight governance execution with temporary worktree isolation,
independent from the main L3 agent chain (Manager/Plan/Run/Review).

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二 (L2)
"""

import asyncio
import os
from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.supervisor_apply import (
    DomainEvent,
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)
from vibe3.domain.publisher import publish
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.supervisor_handoff import (
    SupervisorHandoffIssue,
    SupervisorHandoffService,
)


def handle_supervisor_issue_identified(event: SupervisorIssueIdentified) -> None:
    """Handle SupervisorIssueIdentified event.

    Promote identification into the actual apply-dispatch intent.
    """
    logger.bind(
        domain="events",
        event="supervisor_issue_identified",
        issue=event.issue_number,
        supervisor=event.supervisor_file,
    ).info("Supervisor issue identified")

    publish(
        SupervisorApplyDispatched(
            issue_number=event.issue_number,
            tmux_session=f"vibe3-supervisor-issue-{event.issue_number}",
            supervisor_file=event.supervisor_file,
            actor="system:supervisor",
        )
    )


def handle_supervisor_prompt_rendered(event: SupervisorPromptRendered) -> None:
    """Handle SupervisorPromptRendered event.

    Logs prompt rendering completion.
    """
    logger.bind(
        domain="events",
        event="supervisor_prompt_rendered",
        issue=event.issue_number,
        prompt_length=event.prompt_length,
    ).debug("Supervisor prompt rendered")


def handle_supervisor_apply_dispatched(event: SupervisorApplyDispatched) -> None:
    """Handle SupervisorApplyDispatched event.

    Triggers supervisor handoff execution via SupervisorHandoffService
    and ExecutionCoordinator. Uses unified infrastructure services.

    Schedules the actual dispatch as an async task to avoid blocking the
    event loop with synchronous I/O (build_handoff_payload, acquire_temporary_worktree,
    and coordinator.dispatch_execution are all blocking operations).
    """
    logger.bind(
        domain="events",
        event="supervisor_apply_dispatched",
        issue=event.issue_number,
        tmux=event.tmux_session,
    ).info("Supervisor apply dispatched, scheduling async task")

    def _dispatch_sync() -> None:
        config = OrchestraConfig.from_settings()
        store = SQLiteClient()
        coordinator = ExecutionCoordinator(config, store)
        github = GitHubClient()
        handoff_service = SupervisorHandoffService.from_config(config)

        logger.bind(
            domain="supervisor_handler",
            issue=event.issue_number,
        ).debug("Supervisor handler dispatching handoff via ExecutionCoordinator")

        wt_context = None

        try:
            handoff_issue = SupervisorHandoffIssue(
                number=event.issue_number,
                title=f"Supervisor handoff for issue #{event.issue_number}",
            )

            if config.dry_run:
                logger.bind(domain="supervisor_handler").info(
                    "Dry run: skipping supervisor dispatch"
                )
                return

            prompt, options, task = handoff_service.build_handoff_payload(handoff_issue)
            wt_context = handoff_service.acquire_temporary_worktree(event.issue_number)

            request = ExecutionRequest(
                role="supervisor",
                target_branch=f"issue-{event.issue_number}",
                target_id=event.issue_number,
                execution_name=event.tmux_session,
                prompt=prompt,
                options=options,
                cwd=str(wt_context.path),
                env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
                refs={"task": task, "issue_number": str(event.issue_number)},
                actor="orchestra:supervisor",
                mode="async",
            )

            result = coordinator.dispatch_execution(request)

            if not result.launched:
                raise RuntimeError(
                    f"Failed to launch supervisor execution: {result.reason}"
                )

            try:
                github.add_comment(
                    event.issue_number,
                    f"🔄 Supervisor apply agent dispatched\n\n"
                    f"**Supervisor file**: `{event.supervisor_file}`\n"
                    f"**Session**: `{result.tmux_session}`\n\n"
                    "Apply agent will execute governance actions "
                    "in an isolated worktree.",
                )
            except Exception as comment_exc:
                logger.bind(
                    domain="supervisor_handler",
                    issue=event.issue_number,
                ).warning(
                    f"Supervisor dispatch launched but failed to post comment: "
                    f"{comment_exc}"
                )

            logger.bind(
                domain="supervisor_handler",
                issue=event.issue_number,
            ).success("Supervisor handoff completed successfully")

        except Exception as exc:
            if wt_context:
                handoff_service.release_temporary_worktree(event.issue_number)

            logger.bind(
                domain="supervisor_handler",
                issue=event.issue_number,
            ).exception(f"Supervisor handoff failed: {exc}")

    async def _do_dispatch() -> None:
        await asyncio.to_thread(_dispatch_sync)

    try:
        # Called from within heartbeat's async event loop — schedule as task.
        loop = asyncio.get_running_loop()
        loop.create_task(
            _do_dispatch(),
            name=f"supervisor-dispatch-{event.issue_number}",
        )
    except RuntimeError:
        # No running loop (e.g. tests, direct CLI call) — safe to use asyncio.run().
        asyncio.run(_do_dispatch())


def handle_supervisor_apply_started(event: SupervisorApplyStarted) -> None:
    """Handle SupervisorApplyStarted event.

    Logs apply agent execution start.
    """
    logger.bind(
        domain="events",
        event="supervisor_apply_started",
        issue=event.issue_number,
        worktree=event.worktree_path,
    ).info("Supervisor apply started in isolated worktree")


def handle_supervisor_apply_completed(event: SupervisorApplyCompleted) -> None:
    """Handle SupervisorApplyCompleted event.

    Logs completion and adds summary comment to issue.
    """
    log = logger.bind(
        domain="events",
        event="supervisor_apply_completed",
        issue=event.issue_number,
        outcome=event.outcome,
    )

    if event.outcome == "success":
        log.success("Supervisor apply completed successfully")
    elif event.outcome == "delegated":
        log.info("Supervisor apply delegated to L3 manager chain")
    elif event.outcome == "partial":
        log.warning("Supervisor apply completed with partial success")
    else:
        log.error("Supervisor apply failed")

    # Add summary comment
    actions_text = "\n".join(f"- {action}" for action in event.actions_taken)
    outcome_emoji = (
        "✅"
        if event.outcome == "success"
        else "⚠️" if event.outcome == "partial" else "❌"
    )
    comment = (
        f"{outcome_emoji} Supervisor Apply Completed\n\n"
        f"**Outcome**: {event.outcome}\n\n"
        f"**Actions taken**:\n{actions_text}\n"
    )

    GitHubClient().add_comment(event.issue_number, comment)

    try:
        config = OrchestraConfig.from_settings()
        SupervisorHandoffService.from_config(config).release_temporary_worktree(
            event.issue_number
        )
        log.info(f"Released temporary worktree for issue #{event.issue_number}")
    except Exception as exc:
        log.warning(f"Failed to release temporary worktree: {exc}")


def handle_supervisor_apply_delegated(event: SupervisorApplyDelegated) -> None:
    """Handle SupervisorApplyDelegated event.

    Adds comments to both governance issue and new task issue,
    linking them together.
    """
    logger.bind(
        domain="events",
        event="supervisor_apply_delegated",
        governance_issue=event.governance_issue_number,
        task_issue=event.new_task_issue_number,
        reason=event.reason,
    ).info("Supervisor apply delegated to L3 manager chain")

    # Comment on governance issue
    GitHubClient().add_comment(
        event.governance_issue_number,
        f"↗️ **Delegated to L3 Manager Chain**\n\n"
        f"This issue requires complex changes beyond L2 scope.\n\n"
        f"**New task issue**: #{event.new_task_issue_number}\n"
        f"**Reason**: {event.reason}\n\n"
        "The task will be processed by the manager chain "
        "with full development workflow.",
    )

    # Comment on new task issue (if created by apply agent)
    GitHubClient().add_comment(
        event.new_task_issue_number,
        f"📋 **Delegated from Governance Issue**\n\n"
        f"**Source issue**: #{event.governance_issue_number}\n"
        f"**Reason**: {event.reason}\n\n"
        f"This task was created by supervisor apply agent "
        "for complex code changes.",
    )


def register_supervisor_apply_handlers() -> None:
    """Register all supervisor apply event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "SupervisorIssueIdentified",
        cast(Callable[[DomainEvent], None], handle_supervisor_issue_identified),
    )
    subscribe(
        "SupervisorPromptRendered",
        cast(Callable[[DomainEvent], None], handle_supervisor_prompt_rendered),
    )
    subscribe(
        "SupervisorApplyDispatched",
        cast(Callable[[DomainEvent], None], handle_supervisor_apply_dispatched),
    )
    subscribe(
        "SupervisorApplyStarted",
        cast(Callable[[DomainEvent], None], handle_supervisor_apply_started),
    )
    subscribe(
        "SupervisorApplyCompleted",
        cast(Callable[[DomainEvent], None], handle_supervisor_apply_completed),
    )
    subscribe(
        "SupervisorApplyDelegated",
        cast(Callable[[DomainEvent], None], handle_supervisor_apply_delegated),
    )

    logger.bind(domain="events").info("Supervisor apply event handlers registered")
