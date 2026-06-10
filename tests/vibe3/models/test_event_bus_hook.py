"""Tests for EventPublisher.on_publish hook mechanism."""

from __future__ import annotations

from dataclasses import dataclass

from vibe3.models.domain_events import DomainEvent
from vibe3.models.event_bus import EventPublisher


@dataclass(frozen=True)
class _TestEvent(DomainEvent):
    """Test event for hook tests."""

    value: str = "test"


class TestAddPublishHook:
    """Test add_publish_hook and hook invocation."""

    def setup_method(self) -> None:
        EventPublisher.reset()

    def teardown_method(self) -> None:
        EventPublisher.reset()

    def test_add_publish_hook_receives_events(self) -> None:
        """Hook called on publish()."""
        publisher = EventPublisher()
        received: list[DomainEvent] = []

        def hook(event: DomainEvent) -> None:
            received.append(event)

        publisher.add_publish_hook(hook)
        event = _TestEvent()
        publisher.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_hook_error_does_not_block_handlers(self) -> None:
        """Hook exception caught, handlers still run."""
        publisher = EventPublisher()
        handler_called: list[bool] = []

        def bad_hook(event: DomainEvent) -> None:
            raise RuntimeError("hook failed")

        def handler(event: DomainEvent) -> None:
            handler_called.append(True)

        publisher.add_publish_hook(bad_hook)
        publisher.subscribe("_TestEvent", handler)
        publisher.publish(_TestEvent())

        assert handler_called, "Handler should still run despite hook error"

    def test_remove_publish_hook(self) -> None:
        """Removed hook no longer receives events."""
        publisher = EventPublisher()
        received: list[DomainEvent] = []

        def hook(event: DomainEvent) -> None:
            received.append(event)

        publisher.add_publish_hook(hook)
        publisher.remove_publish_hook(hook)
        publisher.publish(_TestEvent())

        assert len(received) == 0

    def test_hook_deduplicated(self) -> None:
        """Same hook added twice only fires once."""
        publisher = EventPublisher()
        call_count: list[int] = [0]

        def hook(event: DomainEvent) -> None:
            call_count[0] += 1

        publisher.add_publish_hook(hook)
        publisher.add_publish_hook(hook)  # Second add should be deduped
        publisher.publish(_TestEvent())

        assert call_count[0] == 1

    def test_reset_clears_hooks(self) -> None:
        """reset() clears hooks from the instance."""
        publisher = EventPublisher()
        received: list[DomainEvent] = []

        def hook(event: DomainEvent) -> None:
            received.append(event)

        publisher.add_publish_hook(hook)
        EventPublisher.reset()
        new_publisher = EventPublisher()
        new_publisher.publish(_TestEvent())

        assert len(received) == 0

    def test_hooks_fire_before_handlers(self) -> None:
        """Hooks fire before type-specific handlers."""
        publisher = EventPublisher()
        order: list[str] = []

        def hook(event: DomainEvent) -> None:
            order.append("hook")

        def handler(event: DomainEvent) -> None:
            order.append("handler")

        publisher.add_publish_hook(hook)
        publisher.subscribe("_TestEvent", handler)
        publisher.publish(_TestEvent())

        assert order == ["hook", "handler"]
