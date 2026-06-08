"""Adapter shell for backward compatibility.

Re-exports GlobalDispatchCoordinator from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- GlobalDispatchCoordinator: vibe3.domain.dispatch_coordinator.GlobalDispatchCoordinator
- QueueEntry: vibe3.models.QueueEntry
- MAX_INTENTS_PER_TICK: vibe3.domain.dispatch_coordinator.MAX_INTENTS_PER_TICK
"""

import importlib

from vibe3.models import QueueEntry


def __getattr__(name: str) -> object:
    """Lazy import for backward compatibility symbols."""
    if name == "GlobalDispatchCoordinator":
        return getattr(
            importlib.import_module("vibe3.domain"), "GlobalDispatchCoordinator"
        )
    if name == "MAX_INTENTS_PER_TICK":
        return getattr(importlib.import_module("vibe3.domain"), "MAX_INTENTS_PER_TICK")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [  # noqa: F822
    "GlobalDispatchCoordinator",
    "QueueEntry",
    "MAX_INTENTS_PER_TICK",
]
