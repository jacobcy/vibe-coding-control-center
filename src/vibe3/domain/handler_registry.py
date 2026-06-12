"""Handler registration utility to eliminate boilerplate."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from loguru import logger

from vibe3.domain import DomainEvent

T = TypeVar("T", bound=DomainEvent)


def register_handler(event_name: str) -> Callable[
    [Callable[[T], None]],
    Callable[[T], None],
]:
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
    from vibe3.domain import subscribe

    def decorator(
        func: Callable[[T], None],
    ) -> Callable[[T], None]:
        subscribe(event_name, cast(Callable[[DomainEvent], None], func))
        logger.bind(domain="events").info(
            f"{func.__name__} registered for {event_name}"
        )
        return func

    return decorator
