"""Tests for domain events data structures."""

from vibe3.domain.events.flow_lifecycle import (
    IssueFailed,
    ManagerDispatched,
)


def test_issue_failed_event_structure() -> None:
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


def test_issue_failed_with_timestamp() -> None:
    """Test IssueFailed event with custom timestamp."""
    event = IssueFailed(
        issue_number=42,
        reason="execution crashed",
        actor="agent:executor",
        timestamp="2026-04-09T12:00:00Z",
    )

    assert event.timestamp == "2026-04-09T12:00:00Z"


def test_manager_dispatched_event_structure() -> None:
    """Test ManagerDispatched event has correct structure."""
    event = ManagerDispatched(
        issue_number=42,
        branch="task/issue-42",
        trigger_state="ready",
    )

    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.trigger_state == "ready"
