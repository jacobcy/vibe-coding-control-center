"""Event handlers for flow lifecycle events.

Handlers for agent execution events (planner, executor, reviewer).

Note: Worker ref validation and no-op blocking now live in
codeagent_runner.CodeagentExecutionService, which owns the unified sync shell
for command-mode, orchestra sync, and tmux-child execution. Domain event
handlers only provide visibility and failure/block side effects; they do NOT
perform proactive state advancement because the domain event path lacks the
full execution context.
"""

from typing import Callable

from loguru import logger

from vibe3.domain.events.flow_lifecycle import (
    DomainEvent,
    IssueFailed,
    IssueStateChanged,
)
from vibe3.models.orchestration import IssueState
from vibe3.services.issue_failure_service import (
    fail_executor_issue,
    fail_manager_issue,
    fail_planner_issue,
    fail_reviewer_issue,
)


def handle_issue_state_changed(event: IssueStateChanged) -> None:
    """Handle IssueStateChanged event.

    Logs observed state transitions only.
    Syncs issue state to GitHub Project Status field if enabled.
    """
    logger.bind(
        domain="events",
        event="issue_state_changed",
        issue=event.issue_number,
        state=f"{event.from_state} → {event.to_state}",
        actor=event.actor,
    ).info("Observed IssueStateChanged")

    # Sync to GitHub Project status
    _sync_issue_to_project_status(event)


def _sync_issue_to_project_status(event: IssueStateChanged) -> None:
    """Sync issue state to GitHub Project Status field.

    This is a best-effort sync that logs failures but doesn't block the main flow.
    """
    try:
        from vibe3.config.orchestra_settings import load_orchestra_config
        from vibe3.config.settings import VibeConfig
        from vibe3.services.project_status_sync_service import (
            ProjectStatusSyncService,
        )

        config = load_orchestra_config()

        # Check if sync is enabled
        if not config.project_status_sync.enabled:
            return

        # Parse the target state
        try:
            state = IssueState(event.to_state)
        except ValueError:
            logger.bind(
                domain="events",
                operation="sync_issue_to_project_status",
                issue=event.issue_number,
                state=event.to_state,
            ).debug(f"Unknown state '{event.to_state}', skipping project sync")
            return

        # Load GitHub project configuration from VibeConfig
        vibe_config = VibeConfig.get_defaults()
        github_project = vibe_config.github_project

        owner = github_project.owner
        project_number = github_project.project_number
        owner_type = github_project.owner_type

        if not owner or not project_number:
            logger.bind(
                domain="events",
                operation="sync_issue_to_project_status",
            ).debug("GitHub project configuration missing, skipping project sync")
            return

        # Perform sync
        sync_service = ProjectStatusSyncService(
            owner=owner,
            project_number=int(project_number),
            owner_type=owner_type,
            status_field_name=config.project_status_sync.status_field_name,
        )

        sync_service.sync_issue_status(event.issue_number, state)

    except Exception as e:
        logger.bind(
            domain="events",
            operation="sync_issue_to_project_status",
            issue=event.issue_number,
        ).warning(f"Project status sync failed: {e}")


_ROLE_FAIL_DISPATCH: dict[str, Callable[..., None]] = {
    "planner": fail_planner_issue,
    "executor": fail_executor_issue,
    "reviewer": fail_reviewer_issue,
    "manager": fail_manager_issue,
}


def handle_issue_failed(event: IssueFailed) -> None:
    """Handle IssueFailed event.

    Routes to role-specific failure handler based on event.role field.
    Falls back to executor for backward compatibility.
    """
    role = event.role or "executor"
    logger.bind(
        domain="events",
        event="issue_failed",
        issue=event.issue_number,
        role=role,
        reason=event.reason,
    ).info("Handling IssueFailed")

    fail_func = _ROLE_FAIL_DISPATCH.get(role, fail_executor_issue)
    fail_func(
        issue_number=event.issue_number,
        reason=event.reason,
        actor=event.actor,
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

    logger.bind(domain="events").info("Flow lifecycle event handlers registered")
