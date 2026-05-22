"""Periodic check executor for consistency validation and resource cleanup.

Runs two phases on each interval tick:
1. Consistency check: PR merged/closed, issue closed, multi-label detection
2. Resource cleanup: expired worktrees and branches (if enabled)

Replaces the old expired resource cleanup with comprehensive checks including:
- PR merged/closed detection
- Issue closed detection
- Multiple state/* label detection and auto-fix
- Flow consistency checks
- Expired resource cleanup (worktrees, local/remote branches)
"""

from loguru import logger

from vibe3.config.orchestra_config import PeriodicCheckConfig
from vibe3.orchestra.logging import append_orchestra_event


async def execute_periodic_check(
    config: PeriodicCheckConfig,
    tick_number: int,
) -> None:
    """Execute periodic consistency check via vibe3 check.

    This function is called from HeartbeatServer's tick loop when
    tick_number % interval_ticks == 0.

    Args:
        config: Periodic check configuration
        tick_number: Current tick number (for logging)
    """
    # Delay imports to avoid circular dependencies
    from vibe3.clients import SQLiteClient
    from vibe3.services.check_service import CheckService

    # Initialize services
    store = SQLiteClient()

    try:
        service = CheckService(store=store)

        # Run consistency check for all active flows
        logger.bind(domain="orchestra", action="periodic_check").info(
            f"Running periodic consistency check (tick #{tick_number})"
        )

        results = service.verify_all_flows(status="active")

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
    from vibe3.runtime.cleanup_executor import execute_expired_resource_cleanup

    await execute_expired_resource_cleanup(config, tick_number)
