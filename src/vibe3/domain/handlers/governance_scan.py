"""Governance scan domain event handler.

Subscribes to GovernanceScanStarted and dispatches the governance agent
via roles/governance.py + shared dispatch utility.
"""

from typing import Callable, cast

from loguru import logger

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events.flow_lifecycle import DomainEvent
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.execution.contracts import ExecutionLaunchResult


def handle_governance_scan_started(event: GovernanceScanStarted) -> None:
    """Dispatch governance scan via roles/governance.py + shared dispatch."""
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.domain.handlers._shared import dispatch_request
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.flow_dispatch import FlowManager
    from vibe3.roles.governance import build_governance_request
    from vibe3.services.orchestra_status_service import OrchestraStatusService

    config = load_orchestra_config()
    store = SQLiteClient()
    backend = CodeagentBackend()
    registry = SessionRegistryService(store, backend)
    registry.mark_governance_sessions_done_when_tmux_gone()
    live_governance = registry.list_live_governance_sessions()
    if len(live_governance) >= config.governance_max_concurrent:
        from vibe3.orchestra.logging import append_governance_event

        session_names = ", ".join(
            str(session.get("tmux_session") or session.get("session_name") or "?")
            for session in live_governance[:3]
        )
        skip_result = ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason=(
                "governance already running"
                if not session_names
                else f"governance already running ({session_names})"
            ),
            reason_code="governance_already_running",
        )
        append_governance_event(
            f"governance dispatch skipped: tick={event.tick_count} "
            f"reason={skip_result.reason}"
        )
        logger.bind(
            domain="governance_handler",
            tick=event.tick_count,
            live_governance=len(live_governance),
            governance_max=config.governance_max_concurrent,
        ).info("Skipping governance scan because another governance session is live")
        return

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

    result = dispatch_request(
        request,
        handler_domain="governance_handler",
        context={"tick": event.tick_count},
    )

    from vibe3.orchestra.logging import append_governance_event

    if result and result.launched:
        append_governance_event(
            f"governance agent launched: tick={event.tick_count} "
            f"session={result.tmux_session}",
        )
    elif result:
        append_governance_event(
            f"governance dispatch skipped: tick={event.tick_count} "
            f"reason={result.reason}",
        )


def register_governance_scan_handlers() -> None:
    """Register governance scan event handlers."""
    from vibe3.domain.publisher import subscribe

    subscribe(
        "GovernanceScanStarted",
        cast(Callable[[DomainEvent], None], handle_governance_scan_started),
    )
    logger.bind(domain="events").info("Governance scan event handlers registered")
