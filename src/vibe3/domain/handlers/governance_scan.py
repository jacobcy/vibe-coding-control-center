"""Governance scan domain event handler.

Subscribes to GovernanceScanStarted and dispatches the governance agent
via roles/governance.py + shared dispatch utility.
"""

from typing import Callable, cast

from loguru import logger

from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.models.orchestra_config import OrchestraConfig


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Dispatch governance scan via roles/governance.py + shared dispatch."""
    from vibe3.domain.handlers._shared import dispatch_request
    from vibe3.execution.flow_dispatch import FlowManager
    from vibe3.roles.governance import build_governance_request
    from vibe3.services.orchestra_status_service import OrchestraStatusService

    config = OrchestraConfig.from_settings()
    flow_manager = FlowManager(config)
    status_service = OrchestraStatusService(config, orchestrator=flow_manager)
    snapshot = status_service.snapshot()

    try:
        request = build_governance_request(config, event.tick_count, snapshot)
    except Exception as exc:
        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
        ).exception(f"Governance scan failed: {exc}")
        return

    if not request:
        return

    dispatch_request(
        request,
        handler_domain="governance_handler",
        context={"tick": event.tick_count},
    )


def register_governance_scan_handlers() -> None:
    """Register governance scan event handlers."""
    from vibe3.domain.publisher import subscribe

    subscribe(
        "GovernanceScanStarted",
        cast(Callable[[DomainEvent], None], handle_governance_scan_started),
    )
    logger.bind(domain="events").info("Governance scan event handlers registered")
