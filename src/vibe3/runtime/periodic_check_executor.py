"""Periodic check executor for consistency validation and resource cleanup.

Runs two phases on each interval tick:
1. Consistency check: PR merged/closed, issue closed, multi-label detection
   (offloaded to a worker thread to avoid blocking the event loop)
2. Resource cleanup: expired worktrees and branches (delegated to
   execute_expired_resource_cleanup with config flags)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.config import PeriodicCheckConfig
from vibe3.observability import append_orchestra_event
from vibe3.orchestra import CheckServiceProtocol

from .cleanup_executor import execute_expired_resource_cleanup

if TYPE_CHECKING:
    from vibe3.orchestra import CleanupServiceProtocol


async def execute_periodic_check(
    config: PeriodicCheckConfig,
    tick_number: int,
    check_service: CheckServiceProtocol,
    cleanup_service: CleanupServiceProtocol | None = None,
) -> None:
    """Execute periodic consistency check via vibe3 check.

    This function is called from HeartbeatServer's tick loop when
    tick_number % interval_ticks == 0.

    Phase 1 is offloaded to a worker thread to avoid blocking the event loop.

    Args:
        config: Periodic check configuration
        tick_number: Current tick number (for logging)
        check_service: CheckService instance (injected to avoid circular dependency)
    """
    import asyncio

    try:
        logger.bind(domain="orchestra", action="periodic_check").info(
            f"Running periodic consistency check (tick #{tick_number})"
        )

        results = await asyncio.to_thread(
            check_service.verify_all_flows, ["active", "blocked"]
        )

        total = len(results)
        invalid = sum(1 for r in results if not r.is_valid)
        fixed = sum(1 for r in results if r.warnings)

        if invalid > 0 or fixed > 0:
            append_orchestra_event(
                "server",
                (
                    f"tick #{tick_number} periodic check: "
                    f"{invalid}/{total} invalid flows, {fixed} auto-fixed"
                ),
            )
            logger.bind(domain="orchestra", action="periodic_check").info(
                f"Periodic check completed: {invalid}/{total} invalid flows, "
                f"{fixed} auto-fixed"
            )
        else:
            logger.bind(domain="orchestra", action="periodic_check").debug(
                f"Periodic check completed: all {total} flows are healthy"
            )

        # Clean orchestra-scanned labels from issues with assignee
        cleaned = await asyncio.to_thread(
            check_service.clean_orchestra_scanned_with_assignee
        )
        if cleaned > 0:
            logger.bind(domain="orchestra", action="periodic_check").info(
                f"Cleaned orchestra-scanned from {cleaned} issues with assignee"
            )

    except Exception as exc:
        append_orchestra_event(
            "server",
            f"tick #{tick_number} periodic check failed: {exc}",
            level="WARNING",
        )
        logger.bind(domain="orchestra", action="periodic_check").warning(
            f"Periodic check failed: {exc}"
        )

    # Phase 2: Expired resource cleanup (if enabled)
    await execute_expired_resource_cleanup(
        config, tick_number, cleanup_service=cleanup_service
    )
