"""Adapter shell for backward compatibility.

Re-exports GlobalDispatchCoordinator from domain layer.
Re-exports QueueEntry and MAX_INTENTS_PER_TICK for backward compatibility.
This module will be deprecated in a future version.
"""

# Re-export GlobalDispatchCoordinator from domain
from vibe3.domain.dispatch_coordinator import (
    MAX_INTENTS_PER_TICK,
    GlobalDispatchCoordinator,
)

# Re-export QueueEntry from orchestra (still in orchestra layer)
from vibe3.orchestra.queue_entry import QueueEntry

__all__ = ["GlobalDispatchCoordinator", "QueueEntry", "MAX_INTENTS_PER_TICK"]
