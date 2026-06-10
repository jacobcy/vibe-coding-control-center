"""Global event bus for domain events.

Defined here (models layer L6) rather than domain (L3) so that any layer
can publish and subscribe without creating circular dependencies.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from loguru import logger

from vibe3.models.domain_events import DomainEvent

E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], None]
PublishHook = Callable[[DomainEvent], None]


class EventPublisher:
    """Central event publisher with handler registry (singleton)."""

    _instance: EventPublisher | None = None
    _handlers: dict[str, list[Callable[[DomainEvent], None]]]
    _hooks: list[PublishHook]

    def __new__(cls) -> EventPublisher:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._handlers = {}
            cls._instance._hooks = []
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        if cls._instance is not None:
            cls._instance._hooks.clear()
        cls._instance = None

    def subscribe(
        self, event_type: str, handler: Callable[[DomainEvent], None]
    ) -> None:
        """Subscribe a handler to an event type (deduplicates)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def add_publish_hook(self, hook: PublishHook) -> None:
        """Register a hook that fires for every published event."""
        if hook not in self._hooks:
            self._hooks.append(hook)

    def remove_publish_hook(self, hook: PublishHook) -> None:
        """Remove a previously registered publish hook."""
        if hook in self._hooks:
            self._hooks.remove(hook)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers."""
        event_type = type(event).__name__

        # Fire publish hooks before type-specific dispatch
        for hook in self._hooks:
            try:
                hook(event)
            except Exception as e:
                logger.bind(domain="events").error(f"Publish hook failed: {e}")

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
