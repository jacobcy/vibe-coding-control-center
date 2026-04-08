"""Event handlers for supervisor apply events.

Handlers for L2 supervisor handoff service execution chain.

This chain handles lightweight governance execution with temporary worktree isolation,
independent from the main L3 agent chain (Manager/Plan/Run/Review).

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二 (L2)
"""

from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.domain.events.supervisor_apply import (
    DomainEvent,
    SupervisorApplyCompleted,
    SupervisorApplyDelegated,
    SupervisorApplyDispatched,
    SupervisorApplyStarted,
    SupervisorIssueIdentified,
    SupervisorPromptRendered,
)


def handle_supervisor_issue_identified(event: SupervisorIssueIdentified) -> None:
    """Handle SupervisorIssueIdentified event.

    Logs the detection of a governance issue requiring supervisor attention.
    """
    logger.bind(
        domain="events",
        event="supervisor_issue_identified",
        issue=event.issue_number,
        supervisor=event.supervisor_file,
    ).info("Supervisor issue identified")


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

    Adds a comment to the issue indicating supervisor dispatch.
    """
    logger.bind(
        domain="events",
        event="supervisor_apply_dispatched",
        issue=event.issue_number,
        tmux=event.tmux_session,
    ).info("Supervisor apply dispatched")

    # Add comment to issue
    GitHubClient().add_comment(
        event.issue_number,
        f"🔄 Supervisor apply agent dispatched\n\n"
        f"**Supervisor file**: `{event.supervisor_file}`\n"
        f"**Session**: `{event.tmux_session}`\n\n"
        f"Apply agent will execute governance actions in an isolated worktree.",
    )


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
