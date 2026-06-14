"""Pool exhaustion auto-stop logic for HeartbeatServer.

Extracted from heartbeat.py to keep the file within the 400-line CI limit.
"""

from collections.abc import Callable

from vibe3.models import OrchestraConfig
from vibe3.observability import append_orchestra_event


def check_pool_exhaustion(
    coordinator: object | None,
    config: OrchestraConfig,
    exhausted_ticks: int,
    stop_callback: Callable[[], None],
) -> int:
    """Check pool exhaustion and auto-stop if threshold reached.

    Returns updated exhausted_ticks counter.
    """
    if not config.auto_stop_on_exhaustion:
        return exhausted_ticks

    # coordinator is typed as object in HeartbeatServer; use hasattr check
    if hasattr(coordinator, "is_dispatch_paused") and coordinator.is_dispatch_paused():  # type: ignore[union-attr]
        exhausted_ticks += 1
        append_orchestra_event(
            "server",
            f"pool exhausted for {exhausted_ticks} consecutive tick(s)",
        )
        if exhausted_ticks >= config.exhaustion_threshold_ticks:
            append_orchestra_event(
                "server",
                f"pool exhausted for {exhausted_ticks} ticks, stopping server",
            )
            stop_callback()
    else:
        exhausted_ticks = 0

    return exhausted_ticks
