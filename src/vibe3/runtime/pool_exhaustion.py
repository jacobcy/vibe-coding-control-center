"""Pool exhaustion auto-stop logic for HeartbeatServer.

Extracted from heartbeat.py to keep the file within the 400-line CI limit.

Implements sleep mode: when dispatch is paused, enters sleep mode instead of
immediately stopping. Wakes up periodically to check for new work and only stops
after N consecutive wake-up cycles with no dispatchable items.
"""

from collections.abc import Callable

from vibe3.models import OrchestraConfig
from vibe3.observability import append_orchestra_event


def check_pool_exhaustion(
    coordinator: object | None,
    config: OrchestraConfig,
    exhausted_ticks: int,
    sleep_cycles: int,
    stop_callback: Callable[[], None],
) -> tuple[int, int]:
    """Check pool exhaustion and manage sleep mode.

    Returns updated (exhausted_ticks, sleep_cycles) tuple.

    Sleep mode behavior:
    - When dispatch paused: increment exhausted_ticks
    - At exhaustion_threshold_ticks: enter sleep mode (no stop)
    - On wake-up ticks (every sleep_check_interval_ticks): increment sleep_cycles
    - After max_sleep_cycles wake-ups (if > 0): call stop_callback()
    - When dispatch unpaused: reset both counters to 0
    """
    pc = config.pool_exhaustion
    if not pc.auto_stop_on_exhaustion:
        return exhausted_ticks, sleep_cycles

    # coordinator is typed as object in HeartbeatServer; use hasattr check
    if hasattr(coordinator, "is_dispatch_paused") and coordinator.is_dispatch_paused():  # type: ignore[union-attr]
        exhausted_ticks += 1
        append_orchestra_event(
            "server",
            f"pool exhausted for {exhausted_ticks} consecutive tick(s)",
        )

        # Enter sleep mode at threshold (no immediate stop)
        if exhausted_ticks == pc.exhaustion_threshold_ticks:
            append_orchestra_event("server", "entering sleep mode")

        # Wake-up check: every sleep_check_interval_ticks of being paused
        # Note: This exhausted_ticks-based wake-up check may not align perfectly
        # with tick_id-based collection wake-ups in dispatch_coordinator.
        # exhausted_ticks measures wall-clock time since exhaustion started,
        # while tick_id is the absolute server tick count. These counters
        # can diverge when pause doesn't start at a multiple of the interval.
        if exhausted_ticks % pc.sleep_check_interval_ticks == 0:
            sleep_cycles += 1
            append_orchestra_event(
                "server",
                f"sleep wake-up #{sleep_cycles}: still exhausted",
            )
            if pc.max_sleep_cycles > 0 and sleep_cycles >= pc.max_sleep_cycles:
                append_orchestra_event(
                    "server",
                    f"max sleep cycles reached ({pc.max_sleep_cycles}), stopping server",
                )
                stop_callback()
    else:
        exhausted_ticks = 0
        sleep_cycles = 0

    return exhausted_ticks, sleep_cycles
