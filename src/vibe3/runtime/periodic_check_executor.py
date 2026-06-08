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
from vibe3.domain import CheckServiceProtocol
from vibe3.observability import append_orchestra_event

if TYPE_CHECKING:
    pass


async def execute_periodic_check(
    config: PeriodicCheckConfig,
    tick_number: int,
    check_service: CheckServiceProtocol,
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
        # Run consistency check for all active flows
        logger.bind(domain="orchestra", action="periodic_check").info(
            f"Running periodic consistency check (tick #{tick_number})"
        )

        # Offload blocking I/O work to a thread to avoid blocking the event loop
        results = await asyncio.to_thread(
            check_service.verify_all_flows, ["active", "blocked"]
        )

        # Summary logging
        total = len(results)
        invalid = sum(1 for r in results if not r.is_valid)
        fixed = sum(1 for r in results if r.warnings)  # warnings = auto-fixed issues

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
    # Import cleanup executor to reuse existing logic
    from .cleanup_executor import execute_expired_resource_cleanup

    await execute_expired_resource_cleanup(config, tick_number)
