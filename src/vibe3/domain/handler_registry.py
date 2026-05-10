"""Handler registration utility to eliminate boilerplate."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.domain.events import DomainEvent


def register_handler(event_name: str) -> Callable:
    """Decorator to register a handler for an event.

    Eliminates boilerplate of manual subscribe() calls.

    Args:
        event_name: Name of event to subscribe to

    Returns:
        Decorator function

    Example:
        @register_handler("FlowCreated")
        def handle_flow_created(event):
            ...
    """
    from vibe3.domain.publisher import subscribe

    def decorator(func: Callable[[DomainEvent], None]) -> Callable[[DomainEvent], None]:
        subscribe(event_name, func)
        logger.bind(domain="events").info(
            f"{func.__name__} registered for {event_name}"
        )
        return func

    return decorator
