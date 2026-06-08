"""Adapter shell for backward compatibility.

Re-exports GlobalDispatchCoordinator from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- GlobalDispatchCoordinator: vibe3.domain.dispatch_coordinator.GlobalDispatchCoordinator
- QueueEntry: vibe3.models.QueueEntry
- MAX_INTENTS_PER_TICK: vibe3.domain.dispatch_coordinator.MAX_INTENTS_PER_TICK
"""

from typing import TYPE_CHECKING

from vibe3.models import QueueEntry

if TYPE_CHECKING:
    from vibe3.domain import MAX_INTENTS_PER_TICK, GlobalDispatchCoordinator


def __getattr__(name: str) -> object:
    if name == "GlobalDispatchCoordinator":
        from vibe3.domain import GlobalDispatchCoordinator

        return GlobalDispatchCoordinator
    if name == "MAX_INTENTS_PER_TICK":
        from vibe3.domain import MAX_INTENTS_PER_TICK

        return MAX_INTENTS_PER_TICK
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["GlobalDispatchCoordinator", "QueueEntry", "MAX_INTENTS_PER_TICK"]
