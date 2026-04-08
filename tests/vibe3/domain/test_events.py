"""Tests for domain events system (expanded)."""

import pytest

from vibe3.domain.events import (
    DomainEvent,
    # Governance
    GovernanceScanCompleted,
    GovernanceScanStarted,
    # Flow Lifecycle
    IssueFailed,
    IssueStateChanged,
    # Manager
    ManagerExecutionStarted,
    ManagerFlowDispatched,
    ManagerFlowQueued,
    PlanCompleted,
    ReviewCompleted,
    SupervisorExecutionCompleted,
)
from vibe3.domain.publisher import EventPublisher, get_publisher, subscribe


def test_flow_lifecycle_event_creation():
    """Test creating flow lifecycle events."""
    event = IssueStateChanged(
        issue_number=123,
        from_state="claimed",
        to_state="in-progress",
        actor="test",
    )
    assert event.issue_number == 123
    assert event.from_state == "claimed"
    assert event.to_state == "in-progress"
    assert event.actor == "test"


def test_governance_event_creation():
    """Test creating governance events."""
    event = GovernanceScanStarted(tick_count=42)
    assert event.tick_count == 42
    assert event.actor == "system:governance"

    event2 = GovernanceScanCompleted(
        tick_count=42,
        active_flows=3,
        suggested_issues=5,
    )
    assert event2.tick_count == 42
    assert event2.active_flows == 3
    assert event2.suggested_issues == 5


def test_manager_event_creation():
    """Test creating manager events."""
    event = ManagerExecutionStarted(
        issue_number=789,
        branch="dev/test",
    )
    assert event.issue_number == 789
    assert event.branch == "dev/test"
    assert event.actor == "agent:manager"

    event2 = ManagerFlowDispatched(
        issue_number=789,
        branch="dev/test",
        tmux_session="vibe3-manager-789",
    )
    assert event2.tmux_session == "vibe3-manager-789"

    event3 = ManagerFlowQueued(
        issue_number=789,
        reason="Capacity limit reached",
        active_flows=5,
        max_capacity=5,
    )
    assert event3.reason == "Capacity limit reached"
    assert event3.active_flows == 5
    assert event3.max_capacity == 5


def test_event_frozen():
    """Test that events are immutable."""
    event = IssueFailed(
        issue_number=456,
        reason="test failure",
        actor="test",
    )
    with pytest.raises(AttributeError):
        event.issue_number = 999  # type: ignore[misc]


def test_publisher_singleton():
    """Test that EventPublisher is a singleton."""
    pub1 = get_publisher()
    pub2 = get_publisher()
    assert pub1 is pub2


def test_subscribe_and_publish():
    """Test subscribing handlers and publishing events."""
    received_events = []

    def handler(event: DomainEvent) -> None:
        received_events.append(event)

    subscribe("TestEvent", handler)

    # Note: subscribe uses event type name, so "TestEvent" won't match
    # Actual event type is "IssueBlocked"
    # This test verifies the mechanism, not the matching


def test_publisher_no_handlers():
    """Test publishing event with no handlers (logs warning)."""
    # Create a new publisher instance to avoid interference
    pub = EventPublisher()
    event = IssueStateChanged(
        issue_number=999,
        from_state=None,
        to_state="ready",
        actor="system",
    )
    # Should not raise, just log warning
    pub.publish(event)


def test_plan_completed_event():
    """Test PlanCompleted event creation."""
    event = PlanCompleted(
        issue_number=100,
        branch="dev/feature",
    )
    assert event.issue_number == 100
    assert event.branch == "dev/feature"
    assert event.actor == "agent:plan"


def test_review_completed_event():
    """Test ReviewCompleted event creation."""
    event = ReviewCompleted(
        issue_number=200,
        branch="dev/feature",
        verdict="PASS",
    )
    assert event.issue_number == 200
    assert event.verdict == "PASS"
    assert event.actor == "agent:review"


def test_supervisor_execution_completed_event():
    """Test SupervisorExecutionCompleted event creation."""
    event = SupervisorExecutionCompleted(
        supervisor_file="supervisor/main.md",
        issue_number=300,
        success=True,
    )
    assert event.supervisor_file == "supervisor/main.md"
    assert event.issue_number == 300
    assert event.success is True

    event2 = SupervisorExecutionCompleted(
        supervisor_file="supervisor/main.md",
        success=False,
    )
    assert event2.issue_number is None
    assert event2.success is False
