"""Event publisher for domain events.

Publishes events to registered handlers, enabling loose coupling
between event producers (Usecase) and consumers (Services).
"""

from typing import Callable, TypeVar

from loguru import logger

from vibe3.domain.events import DomainEvent

# Event handler type - use TypeVar for type safety
E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], None]


class EventPublisher:
    """Central event publisher with handler registry."""

    _instance: "EventPublisher | None" = None
    _handlers: dict[str, list[Callable[[DomainEvent], None]]]

    def __new__(cls) -> "EventPublisher":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    def subscribe(
        self, event_type: str, handler: Callable[[DomainEvent], None]
    ) -> None:
        """Subscribe a handler to an event type.

        Prevents duplicate handler registration to avoid multiple calls
        for the same event.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        # Deduplication check
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers."""
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


# Convenience functions for direct usage
def get_publisher() -> EventPublisher:
    """Get the global event publisher singleton."""
    return EventPublisher()


def publish(event: DomainEvent) -> None:
    """Publish an event using the global publisher."""
    EventPublisher().publish(event)


def subscribe(event_type: str, handler: Callable[[DomainEvent], None]) -> None:
    """Subscribe to an event type using the global publisher."""
    EventPublisher().subscribe(event_type, handler)
