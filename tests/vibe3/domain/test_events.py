"""Tests for domain events system (expanded)."""

import pytest

from vibe3.domain.events import (
    GovernanceScanCompleted,
    GovernanceScanStarted,
    # Flow Lifecycle
    IssueFailed,
    IssueStateChanged,
    ManagerDispatched,
)
from vibe3.domain.publisher import get_publisher, subscribe


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


def test_governance_scan_started():
    """Test creating governance scan started event."""
    event = GovernanceScanStarted(tick_count=5)
    assert event.tick_count == 5


def test_governance_scan_completed():
    """Test creating governance scan completed event."""
    event = GovernanceScanCompleted(tick_count=10, active_flows=3, suggested_issues=2)
    assert event.tick_count == 10
    assert event.active_flows == 3


def test_event_publisher_singleton():
    """Test EventPublisher singleton pattern."""
    publisher1 = get_publisher()
    publisher2 = get_publisher()
    assert publisher1 is publisher2


def test_subscribe_and_publish():
    """Test subscribing to events and publishing."""
    received_events = []

    def handler(event):  # type: ignore[no-untyped-def]
        received_events.append(event)

    subscribe("IssueStateChanged", handler)

    pub = get_publisher()
    event = IssueStateChanged(
        issue_number=999,
        from_state="ready",
        to_state="claimed",
        actor="test_publisher",
    )
    pub.publish(event)

    assert len(received_events) == 1
    assert received_events[0].issue_number == 999


def test_event_frozen():
    """Test that events are immutable (frozen dataclass)."""
    event = IssueFailed(
        issue_number=42,
        reason="test failure",
        actor="test",
    )
    with pytest.raises(AttributeError):
        event.issue_number = 100  # type: ignore[misc]


def test_manager_dispatched_event_creation():
    """Test creating manager dispatched event."""
    event = ManagerDispatched(
        issue_number=123,
        branch="task/issue-123",
        trigger_state="ready",
    )
    assert event.issue_number == 123
    assert event.branch == "task/issue-123"
    assert event.trigger_state == "ready"
