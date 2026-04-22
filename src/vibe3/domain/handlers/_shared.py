"""Shared dispatch utility for domain event handlers.

Eliminates the repeated config/store/coordinator/dispatch/log boilerplate
across governance_scan, supervisor_scan, and plan/run/review handlers.
"""

from __future__ import annotations

from loguru import logger

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest


def dispatch_request(
    request: ExecutionRequest,
    *,
    handler_domain: str,
    context: dict[str, object] | None = None,
) -> ExecutionLaunchResult | None:
    """Dispatch an ExecutionRequest through a shared coordinator.

    Creates config, store, and coordinator internally, then dispatches.
    Returns None if setup fails (logged as error).

    Args:
        request: Pre-built ExecutionRequest from a role builder.
        handler_domain: Logger domain string (e.g. "governance_handler").
        context: Optional extra fields for structured logging.
    """
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.execution.coordinator import ExecutionCoordinator

    try:
        config = load_orchestra_config()
        store = SQLiteClient()
        coordinator = ExecutionCoordinator(config, store)
    except Exception as exc:
        logger.bind(domain=handler_domain).exception(f"Dispatch setup failed: {exc}")
        return None

    try:
        result = coordinator.dispatch_execution(request)
    except Exception as exc:
        logger.bind(
            domain=handler_domain,
            **(context or {}),
        ).exception(f"Dispatch error: {exc}")
        return None

    log_ctx = {**(context or {})}
    if result.launched:
        log_ctx["tmux_session"] = result.tmux_session
        logger.bind(domain=handler_domain, **log_ctx).success(
            f"Dispatch launched: {request.role}"
        )
    else:
        logger.bind(domain=handler_domain, **log_ctx).warning(
            f"Dispatch not launched: {result.reason}"
        )

    return result
