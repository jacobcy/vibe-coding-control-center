"""Tests for handler registry utility."""

from vibe3.domain.handler_registry import register_handler


def test_register_handler_decorator():
    """register_handler should subscribe function to event."""
    called = []

    @register_handler("TestEvent")
    def my_handler(event):
        called.append(event)

    # Verify function is still callable
    my_handler("test_event")
    assert called == ["test_event"]
