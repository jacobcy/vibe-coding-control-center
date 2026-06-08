"""Event publisher for domain events.

Re-exported from models layer to break L3 circular dependencies.
See vibe3.models.event_bus for the canonical implementation.
"""

from vibe3.models import (
    EventHandler,
    EventPublisher,
    get_publisher,
    publish,
    subscribe,
)

__all__ = [
    "EventHandler",
    "EventPublisher",
    "get_publisher",
    "publish",
    "subscribe",
]
