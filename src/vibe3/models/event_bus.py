"""Global event bus for domain events.

Defined here (models layer L6) rather than domain (L3) so that any layer
can publish and subscribe without creating circular dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeVar

from loguru import logger

from vibe3.domain.events.base import DomainEvent

if TYPE_CHECKING:
    from vibe3.domain.events.coalescing import DispatchCoalescer

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], None]


class EventPublisher:
    """Central event publisher with handler registry (singleton)."""

    _instance: EventPublisher | None = None
    _handlers: dict[str, list[Callable[[DomainEvent], None]]]
    _coalescer: "DispatchCoalescer | None"

    def __new__(cls) -> EventPublisher:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._coalescer = None
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    def set_coalescer(self, coalescer: "DispatchCoalescer | None") -> None:
        """Set or clear the dispatch coalescer.

        Args:
            coalescer: Coalescer instance to use, or None to disable coalescing
        """
        self._coalescer = coalescer

    def subscribe(
        self, event_type: str, handler: Callable[[DomainEvent], None]
    ) -> None:
        """Subscribe a handler to an event type (deduplicates)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers.

        If a coalescer is set and the event is a dispatch intent, the event
        is coalesced (buffered) and may not be immediately published.
        """
        # Coalescing: route through coalescer if set
        if self._coalescer is not None:
            result = self._coalescer.coalesce(event)
            if result is None:
                # Event was absorbed into buffer or buffered for later
                return
            # result is event itself (pass-through for non-dispatch-intent)
            event = result

        event_type = type(event).__name__
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.bind(domain="events").warning(
                f"No handlers registered for event: {event_type}"
            )
            return

        logger.bind(domain="events").info(
            f"Publishing {event_type} to {len(handlers)} handler(s)"
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.bind(domain="events").error(
                    f"Handler failed for {event_type}: {e}"
                )


def get_publisher() -> EventPublisher:
    """Get the global event publisher singleton."""
    return EventPublisher()


def publish(event: DomainEvent) -> None:
    """Publish an event using the global publisher."""
    EventPublisher().publish(event)


def subscribe(event_type: str, handler: Callable[[DomainEvent], None]) -> None:
    """Subscribe to an event type using the global publisher."""
    EventPublisher().subscribe(event_type, handler)
