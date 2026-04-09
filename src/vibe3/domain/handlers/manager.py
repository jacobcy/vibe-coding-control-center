"""Event handlers for manager dispatch."""

from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.domain.events import DomainEvent
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def handle_issue_state_changed_for_manager(event: IssueStateChanged) -> None:
    """Dispatch manager when an issue enters claimed state."""
    if event.to_state != "claimed":
        return

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        from_state=event.from_state,
        to_state=event.to_state,
    ).info("Manager handler triggered for claimed issue")

    config = OrchestraConfig.from_settings()
    github_client = GitHubClient()
    issue_data = github_client.view_issue(event.issue_number)

    if issue_data is None or isinstance(issue_data, str):
        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
            error="issue_not_found",
        ).error("Failed to fetch issue details from GitHub")
        return

    issue_info = IssueInfo.from_github_payload(issue_data)

    if issue_info is None:
        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
            error="invalid_issue_data",
        ).error("Failed to parse issue data from GitHub response")
        return

    issue_info.state = IssueState.CLAIMED
    manager_executor = ManagerExecutor(config)

    try:
        dispatch_result = manager_executor.dispatch_manager(issue_info)

        if dispatch_result:
            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
            ).success("Manager execution completed via domain event")
        else:
            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
            ).warning("Manager dispatch returned False")

    except Exception as exc:
        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
        ).exception(f"Manager dispatch failed: {exc}")


def register_manager_handlers() -> None:
    """Register all manager event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    # Subscribe to IssueStateChanged for manager trigger
    subscribe(
        "IssueStateChanged",
        cast(Callable[[DomainEvent], None], handle_issue_state_changed_for_manager),
    )

    logger.bind(domain="events").info("Manager event handlers registered")
