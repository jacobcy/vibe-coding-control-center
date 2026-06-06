"""Tests for dispatch intent coalescing."""

from vibe3.domain.events.coalescing import CoalesceRecord, DispatchCoalescer
from vibe3.domain.events.flow_lifecycle import (
    ExecutorDispatchIntent,
    PlannerDispatchIntent,
)
from vibe3.domain.events.governance import GovernanceScanStarted


class TestDispatchCoalescer:
    """Test DispatchCoalescer behavior."""

    def test_multiple_same_type_same_issue_coalesced(self) -> None:
        """Multiple same-type dispatch intents for same issue → one effective event."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        event2 = PlannerDispatchIntent(
            issue_number=123, branch="feature-2", trigger_state="claimed"
        )
        event3 = PlannerDispatchIntent(
            issue_number=123, branch="feature-3", trigger_state="claimed"
        )

        # First event is buffered
        result1 = coalescer.coalesce(event1)
        assert result1 is None

        # Second event merges with first (absorbed)
        result2 = coalescer.coalesce(event2)
        assert result2 is None

        # Third event merges with previous (absorbed)
        result3 = coalescer.coalesce(event3)
        assert result3 is None

        # Flush returns only one event (latest)
        events = coalescer.flush()
        assert len(events) == 1
        assert events[0].branch == "feature-3"  # Latest wins

        # End tick records the merge
        records = coalescer.end_tick()
        assert len(records) == 1
        assert records[0].issue_number == 123
        assert records[0].event_type == "PlannerDispatchIntent"
        assert records[0].merged_count == 2  # Two events merged into final

    def test_different_types_same_issue_both_retained(self) -> None:
        """Different event types for same issue → both retained."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        planner_event = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        executor_event = ExecutorDispatchIntent(
            issue_number=123, branch="feature-2", trigger_state="in-progress"
        )

        result1 = coalescer.coalesce(planner_event)
        assert result1 is None

        result2 = coalescer.coalesce(executor_event)
        assert result2 is None

        # Flush returns both events (different types)
        events = coalescer.flush()
        assert len(events) == 2

        event_types = {type(e).__name__ for e in events}
        assert event_types == {"PlannerDispatchIntent", "ExecutorDispatchIntent"}

        # No coalescing occurred (different types)
        records = coalescer.end_tick()
        assert len(records) == 0

    def test_different_issues_both_retained(self) -> None:
        """Different issues → both retained."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        event2 = PlannerDispatchIntent(
            issue_number=456, branch="feature-2", trigger_state="claimed"
        )

        result1 = coalescer.coalesce(event1)
        assert result1 is None

        result2 = coalescer.coalesce(event2)
        assert result2 is None

        # Flush returns both events (different issues)
        events = coalescer.flush()
        assert len(events) == 2

        issue_numbers = {e.issue_number for e in events}
        assert issue_numbers == {123, 456}

        # No coalescing occurred (different issues)
        records = coalescer.end_tick()
        assert len(records) == 0

    def test_latest_payload_wins(self) -> None:
        """Latest payload wins: second event's fields replace first."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        event2 = PlannerDispatchIntent(
            issue_number=123, branch="feature-2-updated", trigger_state="claimed"
        )

        coalescer.coalesce(event1)
        coalescer.coalesce(event2)

        events = coalescer.flush()
        assert len(events) == 1
        assert events[0].branch == "feature-2-updated"  # Latest payload

    def test_non_dispatch_intent_passes_through(self) -> None:
        """Non-dispatch-intent events pass through unbuffered."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        # GovernanceScanStarted does not have issue_number attribute
        event = GovernanceScanStarted(tick_count=1, execution_count=1)

        result = coalescer.coalesce(event)
        assert result is event  # Pass-through (returns event itself)

        # Flush returns empty (nothing buffered)
        events = coalescer.flush()
        assert len(events) == 0

    def test_start_tick_resets_buffer(self) -> None:
        """start_tick() resets the buffer."""
        coalescer = DispatchCoalescer()

        # First tick
        coalescer.start_tick(tick_id=1)
        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        coalescer.coalesce(event1)
        coalescer.end_tick()

        # Second tick - buffer should be reset
        coalescer.start_tick(tick_id=2)
        event2 = PlannerDispatchIntent(
            issue_number=456, branch="feature-2", trigger_state="claimed"
        )
        coalescer.coalesce(event2)

        events = coalescer.flush()
        assert len(events) == 1
        assert events[0].issue_number == 456  # Only second tick's event

    def test_end_tick_returns_coalesce_records(self) -> None:
        """end_tick() returns coalesce records with correct stats."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        # Issue 123: 3 events → 1 final (2 merged)
        for i in range(3):
            coalescer.coalesce(
                PlannerDispatchIntent(
                    issue_number=123,
                    branch=f"feature-{i}",
                    trigger_state="claimed",
                )
            )

        # Issue 456: 2 events → 1 final (1 merged)
        for i in range(2):
            coalescer.coalesce(
                PlannerDispatchIntent(
                    issue_number=456,
                    branch=f"feature-{i}",
                    trigger_state="claimed",
                )
            )

        # Issue 789: 1 event → 1 final (0 merged)
        coalescer.coalesce(
            PlannerDispatchIntent(
                issue_number=789, branch="feature-0", trigger_state="claimed"
            )
        )

        coalescer.flush()
        records = coalescer.end_tick()

        # Only issues with merged events appear in records
        assert len(records) == 2

        record_dict = {r.issue_number: r for r in records}
        assert record_dict[123].merged_count == 2
        assert record_dict[456].merged_count == 1
        assert 789 not in record_dict  # No merges for issue 789

    def test_empty_tick_no_records(self) -> None:
        """Empty tick produces no coalesce records."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        coalescer.flush()
        records = coalescer.end_tick()
        assert len(records) == 0

    def test_start_tick_twice_logs_warning(self) -> None:
        """start_tick() called twice without end_tick() logs warning but safe."""
        coalescer = DispatchCoalescer()

        coalescer.start_tick(tick_id=1)
        event1 = PlannerDispatchIntent(
            issue_number=123, branch="feature-1", trigger_state="claimed"
        )
        coalescer.coalesce(event1)

        # Call start_tick again without end_tick (should log warning)
        coalescer.start_tick(tick_id=2)

        # Buffer should be reset
        event2 = PlannerDispatchIntent(
            issue_number=456, branch="feature-2", trigger_state="claimed"
        )
        coalescer.coalesce(event2)

        events = coalescer.flush()
        assert len(events) == 1
        assert events[0].issue_number == 456  # Only second tick's event

    def test_coalesce_record_payload_summary(self) -> None:
        """CoalesceRecord correctly extracts payload summary."""
        coalescer = DispatchCoalescer()
        coalescer.start_tick(tick_id=1)

        event = PlannerDispatchIntent(
            issue_number=123,
            branch="feature-1",
            trigger_state="claimed",
            actor="test-actor",
        )
        coalescer.coalesce(event)

        # Modify event to test summary extraction
        event2 = PlannerDispatchIntent(
            issue_number=123,
            branch="feature-2",
            trigger_state="claimed",
            actor="test-actor-2",
        )
        coalescer.coalesce(event2)

        coalescer.flush()
        records = coalescer.end_tick()

        assert len(records) == 1
        record = records[0]
        assert record.issue_number == 123
        assert record.event_type == "PlannerDispatchIntent"
        assert record.kept_payload_summary["issue_number"] == "123"
        assert record.kept_payload_summary["branch"] == "feature-2"
        assert record.kept_payload_summary["trigger_state"] == "claimed"
        assert record.kept_payload_summary["actor"] == "test-actor-2"


class TestCoalesceRecord:
    """Test CoalesceRecord dataclass."""

    def test_coalesce_record_creation(self) -> None:
        """CoalesceRecord stores correct values."""
        record = CoalesceRecord(
            issue_number=123,
            event_type="PlannerDispatchIntent",
            merged_count=2,
            kept_payload_summary={"branch": "feature-3"},
        )

        assert record.issue_number == 123
        assert record.event_type == "PlannerDispatchIntent"
        assert record.merged_count == 2
        assert record.kept_payload_summary == {"branch": "feature-3"}
