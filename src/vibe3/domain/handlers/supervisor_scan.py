"""Supervisor scan domain event handler.

Subscribes to SupervisorIssueIdentified and dispatches the supervisor apply
agent via roles/supervisor.py + shared dispatch utility.
"""

from typing import Callable, cast

from loguru import logger

from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.models.orchestra_config import OrchestraConfig


def handle_supervisor_issue_identified(event: SupervisorIssueIdentified) -> None:
    """Dispatch supervisor apply via roles/supervisor.py + shared dispatch."""
    from vibe3.domain.handlers._shared import dispatch_request
    from vibe3.roles.supervisor import build_supervisor_apply_request

    config = OrchestraConfig.from_settings()
    if config.dry_run:
        logger.bind(
            domain="supervisor_handler",
            issue_number=event.issue_number,
        ).info("Dry run: skipping supervisor apply dispatch")
        return

    try:
        request = build_supervisor_apply_request(
            config,
            event.issue_number,
            issue_title=event.issue_title,
        )
    except Exception as exc:
        logger.bind(
            domain="supervisor_handler",
            issue_number=event.issue_number,
        ).exception(f"Supervisor apply dispatch failed: {exc}")
        return

    dispatch_request(
        request,
        handler_domain="supervisor_handler",
        context={"issue_number": event.issue_number},
    )


def register_supervisor_scan_handlers() -> None:
    """Register supervisor scan event handlers."""
    from vibe3.domain.publisher import subscribe

    subscribe(
        "SupervisorIssueIdentified",
        cast(Callable[[DomainEvent], None], handle_supervisor_issue_identified),
    )
    logger.bind(domain="events").info("Supervisor scan event handlers registered")
