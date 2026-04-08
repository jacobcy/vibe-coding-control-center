"""Event handlers for manager events.

Handlers for manager execution and flow dispatching.
"""

from typing import Callable

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.domain.events.manager import (
    DomainEvent,
    ManagerExecutionCompleted,
    ManagerExecutionStarted,
    ManagerFlowDispatched,
    ManagerFlowQueued,
)
from vibe3.services.flow_service import FlowService


def handle_manager_execution_started(event: ManagerExecutionStarted) -> None:
    """Handle ManagerExecutionStarted event.

    Logs manager execution start and updates flow state.
    """
    logger.bind(
        domain="events",
        event="manager_execution_started",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Manager execution started")

    # Record event in flow history
    flow_service = FlowService()
    flow_service.store.add_event(
        event.branch,
        "manager_started",
        event.actor,
        detail=f"Manager started processing issue #{event.issue_number}",
        refs={"issue": str(event.issue_number)},
    )


def handle_manager_execution_completed(event: ManagerExecutionCompleted) -> None:
    """Handle ManagerExecutionCompleted event.

    Logs manager execution completion and updates flow state.
    """
    logger.bind(
        domain="events",
        event="manager_execution_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).success("Manager execution completed")

    # Record event in flow history
    flow_service = FlowService()
    flow_service.store.add_event(
        event.branch,
        "manager_completed",
        event.actor,
        detail=f"Manager completed processing issue #{event.issue_number}",
        refs={"issue": str(event.issue_number)},
    )


def handle_manager_flow_dispatched(event: ManagerFlowDispatched) -> None:
    """Handle ManagerFlowDispatched event.

    Logs flow dispatch and adds comment to issue.
    """
    logger.bind(
        domain="events",
        event="manager_flow_dispatched",
        issue=event.issue_number,
        branch=event.branch,
        tmux=event.tmux_session,
    ).info("Manager flow dispatched")

    # Add comment to issue
    GitHubClient().add_comment(
        event.issue_number,
        f"🚀 Manager dispatched flow to tmux session: `{event.tmux_session}`\n\n"
        f"Branch: `{event.branch}`",
    )


def handle_manager_flow_queued(event: ManagerFlowQueued) -> None:
    """Handle ManagerFlowQueued event.

    Logs flow queue and adds comment to issue.
    """
    logger.bind(
        domain="events",
        event="manager_flow_queued",
        issue=event.issue_number,
        reason=event.reason,
        active_flows=event.active_flows,
        capacity=event.max_capacity,
    ).warning("Manager flow queued due to capacity")

    # Add comment to issue
    GitHubClient().add_comment(
        event.issue_number,
        f"⏳ Flow queued due to capacity limit\n\n"
        f"**Reason**: {event.reason}\n"
        f"**Active flows**: {event.active_flows}/{event.max_capacity}\n\n"
        f"Flow will be dispatched when capacity becomes available.",
    )


def register_manager_handlers() -> None:
    """Register all manager event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "ManagerExecutionStarted",
        cast(Callable[[DomainEvent], None], handle_manager_execution_started),
    )
    subscribe(
        "ManagerExecutionCompleted",
        cast(Callable[[DomainEvent], None], handle_manager_execution_completed),
    )
    subscribe(
        "ManagerFlowDispatched",
        cast(Callable[[DomainEvent], None], handle_manager_flow_dispatched),
    )
    subscribe(
        "ManagerFlowQueued",
        cast(Callable[[DomainEvent], None], handle_manager_flow_queued),
    )

    logger.bind(domain="events").info("Manager event handlers registered")
