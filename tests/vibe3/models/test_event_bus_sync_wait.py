"""Test EventBus publish_and_wait() functionality."""

from vibe3.models import DomainEvent, EventPublisher, publish_and_wait, subscribe


class TestPublishAndWait:
    """Tests for publish_and_wait() method."""

    def setup_method(self) -> None:
        """Reset EventPublisher singleton before each test."""
        EventPublisher.reset()

    def test_publish_and_wait_returns_handler_result(self) -> None:
        """Handler returns ExecutionLaunchResult, verify correct return."""
        from vibe3.models import ExecutionLaunchResult

        # Track handler invocation
        handler_called = []

        def handler(event: DomainEvent) -> ExecutionLaunchResult:
            handler_called.append(True)
            return ExecutionLaunchResult(
                launched=True,
                tmux_session="test-session",
                log_path="/tmp/test.log",
            )

        # Subscribe handler
        subscribe("TestEvent", handler)

        # Create and publish event
        class TestEvent(DomainEvent):
            test_field: str = "test"

        event = TestEvent()
        result = publish_and_wait(event)

        # Verify handler was called
        assert len(handler_called) == 1

        # Verify result
        assert result is not None
        assert isinstance(result, ExecutionLaunchResult)
        assert result.launched is True
        assert result.tmux_session == "test-session"
        assert result.log_path == "/tmp/test.log"

    def test_publish_and_wait_no_handlers(self) -> None:
        """No handler registered, returns None."""

        # Create event without any handler
        class NoHandlerEvent(DomainEvent):
            test_field: str = "test"

        event = NoHandlerEvent()
        result = publish_and_wait(event)

        # Verify returns None
        assert result is None

    def test_publish_and_wait_first_non_none_returned(self) -> None:
        """Multiple handlers, take first non-None value."""
        from vibe3.models import ExecutionLaunchResult

        call_order = []

        def handler1(event: DomainEvent) -> None:
            call_order.append("handler1")
            # Returns None (explicitly)

        def handler2(event: DomainEvent) -> ExecutionLaunchResult:
            call_order.append("handler2")
            return ExecutionLaunchResult(
                launched=True,
                tmux_session="session2",
            )

        def handler3(event: DomainEvent) -> ExecutionLaunchResult:
            call_order.append("handler3")
            return ExecutionLaunchResult(
                launched=True,
                tmux_session="session3",
            )

        # Subscribe all handlers
        subscribe("MultiHandlerEvent", handler1)
        subscribe("MultiHandlerEvent", handler2)
        subscribe("MultiHandlerEvent", handler3)

        # Create and publish event
        class MultiHandlerEvent(DomainEvent):
            test_field: str = "test"

        event = MultiHandlerEvent()
        result = publish_and_wait(event)

        # Verify first non-None result is returned
        assert result is not None
        assert result.tmux_session == "session2"

        # Verify handlers were called until first non-None result
        # (handler3 should NOT be called since handler2 returned non-None)
        assert call_order == ["handler1", "handler2"]

    def test_publish_and_wait_preserves_existing_behavior(self) -> None:
        """publish() continues to work and ignores return values."""
        from vibe3.models import ExecutionLaunchResult

        handler_called = []

        def handler(event: DomainEvent) -> ExecutionLaunchResult:
            handler_called.append(True)
            return ExecutionLaunchResult(launched=True)

        # Subscribe handler
        subscribe("ExistingEvent", handler)

        # Create and publish event using publish() (not publish_and_wait)
        class ExistingEvent(DomainEvent):
            test_field: str = "test"

        from vibe3.models import publish

        event = ExistingEvent()
        publish(event)  # Should not raise or return anything

        # Verify handler was called
        assert len(handler_called) == 1

    def test_publish_and_wait_with_exception_in_handler(self) -> None:
        """Handler raises exception, should log error and continue."""
        from vibe3.models import ExecutionLaunchResult

        call_order = []

        def failing_handler(event: DomainEvent) -> None:
            call_order.append("failing")
            raise RuntimeError("Handler error")

        def working_handler(event: DomainEvent) -> ExecutionLaunchResult:
            call_order.append("working")
            return ExecutionLaunchResult(launched=True)

        # Subscribe both handlers
        subscribe("ExceptionEvent", failing_handler)
        subscribe("ExceptionEvent", working_handler)

        # Create and publish event
        class ExceptionEvent(DomainEvent):
            test_field: str = "test"

        event = ExceptionEvent()
        result = publish_and_wait(event)

        # Verify both handlers were attempted
        assert call_order == ["failing", "working"]

        # Verify second handler's result is returned
        assert result is not None
        assert result.launched is True
