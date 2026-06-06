"""Integration tests for publisher + coalescer flow."""

from vibe3.domain import get_publisher
from vibe3.domain.events.coalescing import DispatchCoalescer
from vibe3.domain.events.flow_lifecycle import PlannerDispatchIntent


class TestPublisherCoalescerIntegration:
    """Test EventPublisher + DispatchCoalescer integration."""

    def test_publish_with_coalescer_buffers_dispatch_intents(self) -> None:
        """Dispatch intents are buffered when coalescer is set."""
        publisher = get_publisher()
        publisher.reset()
        publisher = get_publisher()

        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)
        publisher.set_coalescer(coalescer)

        # Track if handler is called
        handler_called = []
        event_type = "PlannerDispatchIntent"

        def handler(event: PlannerDispatchIntent) -> None:
            handler_called.append(event)

        publisher.subscribe(event_type, handler)

        event = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        publisher.publish(event)

        # Event should be buffered, not delivered to handler
        assert len(handler_called) == 0

        # Flush and clear coalescer
        buffered = coalescer.flush()
        assert len(buffered) == 1
        assert buffered[0].issue_number == 123

        publisher.set_coalescer(None)
        publisher.reset()

    def test_publish_without_coalescer_delivers_immediately(self) -> None:
        """Events are delivered immediately when no coalescer is set."""
        publisher = get_publisher()
        publisher.reset()
        publisher = get_publisher()

        # No coalescer set
        handler_called = []
        event_type = "PlannerDispatchIntent"

        def handler(event: PlannerDispatchIntent) -> None:
            handler_called.append(event)

        publisher.subscribe(event_type, handler)

        event = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        publisher.publish(event)

        # Event should be delivered immediately
        assert len(handler_called) == 1
        assert handler_called[0].issue_number == 123

        publisher.reset()

    def test_flush_and_republish_delivers_to_handlers(self) -> None:
        """Flushed events republished without coalescer reach handlers."""
        publisher = get_publisher()
        publisher.reset()
        publisher = get_publisher()

        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        # Track handler calls
        handler_called = []
        event_type = "PlannerDispatchIntent"

        def handler(event: PlannerDispatchIntent) -> None:
            handler_called.append(event)

        publisher.subscribe(event_type, handler)

        # Publish multiple events for same issue
        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        event2 = PlannerDispatchIntent(
            issue_number=123, branch="feature-2", trigger_state="claimed"
        )

        publisher.set_coalescer(coalescer)
        publisher.publish(event1)
        publisher.publish(event2)

        # No events delivered yet (buffered)
        assert len(handler_called) == 0

        # Flush and clear coalescer BEFORE republishing
        buffered = coalescer.flush()
        publisher.set_coalescer(None)

        # Republish flushed events (should reach handlers now)
        for event in buffered:
            publisher.publish(event)

        # Latest event should be delivered
        assert len(handler_called) == 1
        assert handler_called[0].branch == "feature-2"  # Latest wins

        publisher.reset()

    def test_non_dispatch_intent_passes_through_with_coalescer(self) -> None:
        """Non-dispatch-intent events pass through even with coalescer set."""
        from vibe3.domain.events.governance import GovernanceScanStarted

        publisher = get_publisher()
        publisher.reset()
        publisher = get_publisher()

        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)
        publisher.set_coalescer(coalescer)

        # Track handler calls
        handler_called = []
        event_type = "GovernanceScanStarted"

        def handler(event: GovernanceScanStarted) -> None:
            handler_called.append(event)

        publisher.subscribe(event_type, handler)

        event = GovernanceScanStarted(tick_count=1, execution_count=1)
        publisher.publish(event)

        # Event should be delivered immediately (pass-through)
        assert len(handler_called) == 1

        # Flush should return empty (nothing buffered)
        buffered = coalescer.flush()
        assert len(buffered) == 0

        publisher.set_coalescer(None)
        publisher.reset()

    def test_multiple_event_types_for_same_issue_all_delivered(self) -> None:
        """Different event types for same issue are all delivered after flush."""
        from vibe3.domain.events.flow_lifecycle import ExecutorDispatchIntent

        publisher = get_publisher()
        publisher.reset()
        publisher = get_publisher()

        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        # Track handler calls
        planner_handler_called = []
        executor_handler_called = []

        def planner_handler(event: PlannerDispatchIntent) -> None:
            planner_handler_called.append(event)

        def executor_handler(event: ExecutorDispatchIntent) -> None:
            executor_handler_called.append(event)

        publisher.subscribe("PlannerDispatchIntent", planner_handler)
        publisher.subscribe("ExecutorDispatchIntent", executor_handler)

        # Publish different types for same issue
        planner_event = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        executor_event = ExecutorDispatchIntent(
            issue_number=123, branch="feature-2", trigger_state="in-progress"
        )

        publisher.set_coalescer(coalescer)
        publisher.publish(planner_event)
        publisher.publish(executor_event)

        # No events delivered yet
        assert len(planner_handler_called) == 0
        assert len(executor_handler_called) == 0

        # Flush and clear coalescer before republishing
        buffered = coalescer.flush()
        publisher.set_coalescer(None)

        # Republish all flushed events
        for event in buffered:
            publisher.publish(event)

        # Both events should be delivered (different types)
        assert len(planner_handler_called) == 1
        assert len(executor_handler_called) == 1

        publisher.reset()
