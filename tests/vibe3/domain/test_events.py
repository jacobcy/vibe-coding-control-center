"""Tests for domain events system (expanded)."""

import pytest

from vibe3.domain.events.flow_lifecycle import (
    IssueFailed,
    ManagerDispatchIntent,
)
from vibe3.domain.events.governance import (
    GovernanceScanCompleted,
    GovernanceScanStarted,
)
from vibe3.domain.publisher import get_publisher, subscribe


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

    subscribe("IssueFailed", handler)

    pub = get_publisher()
    event = IssueFailed(
        issue_number=999,
        reason="test failure",
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


def test_manager_dispatch_intent_event_creation():
    """Test creating manager dispatch intent event."""
    event = ManagerDispatchIntent(
        issue_number=123,
        branch="task/issue-123",
        trigger_state="ready",
    )
    assert event.issue_number == 123
    assert event.branch == "task/issue-123"
    assert event.trigger_state == "ready"


def test_issue_failed_event_structure():
    """Test IssueFailed event has correct structure."""
    event = IssueFailed(
        issue_number=42,
        reason="execution crashed",
        actor="agent:executor",
        role="executor",
    )

    assert event.issue_number == 42
    assert event.reason == "execution crashed"
    assert event.actor == "agent:executor"
    assert event.role == "executor"
    assert event.timestamp is None


def test_issue_failed_with_timestamp():
    """Test IssueFailed event with custom timestamp."""
    event = IssueFailed(
        issue_number=42,
        reason="execution crashed",
        actor="agent:executor",
        timestamp="2026-04-09T12:00:00Z",
    )

    assert event.timestamp == "2026-04-09T12:00:00Z"
