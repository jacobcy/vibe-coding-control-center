"""Adapter shell for backward compatibility.

.. deprecated:: 3.0.0
    Use vibe3.domain.GlobalDispatchCoordinator instead.
    This module will be removed in a future version.
"""

import warnings

# Re-export GlobalDispatchCoordinator from domain
from vibe3.domain.dispatch_coordinator import (
    MAX_INTENTS_PER_TICK,
    GlobalDispatchCoordinator,
)

# Re-export QueueEntry from orchestra (still in orchestra layer)
from vibe3.orchestra.queue_entry import QueueEntry

# Emit deprecation warning when module is imported
warnings.warn(
    "Importing GlobalDispatchCoordinator from "
    "orchestra.global_dispatch_coordinator is deprecated. "
    "Use 'from vibe3.domain import GlobalDispatchCoordinator' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["GlobalDispatchCoordinator", "QueueEntry", "MAX_INTENTS_PER_TICK"]
