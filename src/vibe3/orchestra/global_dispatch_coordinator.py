"""Adapter shell for backward compatibility.

Re-exports GlobalDispatchCoordinator from domain layer for legacy imports.
All symbols are also available from their canonical locations:
- GlobalDispatchCoordinator: vibe3.domain.dispatch_coordinator.GlobalDispatchCoordinator
- QueueEntry: vibe3.models.QueueEntry
- MAX_INTENTS_PER_TICK: vibe3.domain.dispatch_coordinator.MAX_INTENTS_PER_TICK
"""

# Re-export GlobalDispatchCoordinator from domain
from vibe3.domain import MAX_INTENTS_PER_TICK, GlobalDispatchCoordinator
from vibe3.models import QueueEntry

__all__ = ["GlobalDispatchCoordinator", "QueueEntry", "MAX_INTENTS_PER_TICK"]
