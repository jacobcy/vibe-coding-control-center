"""Tests for domain events system (expanded)."""

import pytest

from vibe3.domain import (
    FlowBlocked,
    FlowCompleted,
    GovernanceScanCompleted,
    GovernanceScanStarted,
    IssueFailed,
    ManagerDispatchIntent,
    PolicyChanged,
    PRMerged,
    get_publisher,
    subscribe,
)


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


# Tests for new flow lifecycle events


def test_flow_blocked_event_construction():
    """Test creating FlowBlocked event with required fields."""
    event = FlowBlocked(
        issue_number=123,
        branch="task/issue-123",
        blocked_reason="dependency issue",
    )
    assert event.issue_number == 123
    assert event.branch == "task/issue-123"
    assert event.blocked_reason == "dependency issue"
    assert event.actor == "system:flow"
    assert event.timestamp is None


def test_flow_completed_event_construction():
    """Test creating FlowCompleted event with required fields."""
    event = FlowCompleted(
        issue_number=456,
        branch="task/issue-456",
        completed_state="done",
    )
    assert event.issue_number == 456
    assert event.branch == "task/issue-456"
    assert event.completed_state == "done"
    assert event.actor == "system:flow"
    assert event.timestamp is None


def test_pr_merged_event_construction():
    """Test creating PRMerged event with required fields."""
    event = PRMerged(
        issue_number=789,
        branch="task/issue-789",
        pr_number=42,
    )
    assert event.issue_number == 789
    assert event.branch == "task/issue-789"
    assert event.pr_number == 42
    assert event.merged_by is None
    assert event.actor == "system:check"
    assert event.timestamp is None


def test_policy_changed_event_construction():
    """Test creating PolicyChanged event with required fields."""
    event = PolicyChanged(
        changed_files=("config/policies/test.yaml", "config/policies/rules.yaml"),
    )
    assert event.changed_files == (
        "config/policies/test.yaml",
        "config/policies/rules.yaml",
    )
    assert event.scope == ()
    assert event.actor == "system:policy"
    assert event.timestamp is None


def test_flow_blocked_event_frozen():
    """Test that FlowBlocked event is immutable."""
    event = FlowBlocked(
        issue_number=1,
        branch="test",
        blocked_reason="test",
    )
    with pytest.raises(AttributeError):
        event.issue_number = 999  # type: ignore[misc]


def test_flow_completed_event_frozen():
    """Test that FlowCompleted event is immutable."""
    event = FlowCompleted(
        issue_number=1,
        branch="test",
        completed_state="done",
    )
    with pytest.raises(AttributeError):
        event.issue_number = 999  # type: ignore[misc]


def test_pr_merged_event_frozen():
    """Test that PRMerged event is immutable."""
    event = PRMerged(
        issue_number=1,
        branch="test",
        pr_number=1,
    )
    with pytest.raises(AttributeError):
        event.issue_number = 999  # type: ignore[misc]


def test_policy_changed_event_frozen():
    """Test that PolicyChanged event is immutable."""
    event = PolicyChanged(changed_files=("test.yaml",))
    with pytest.raises(AttributeError):
        event.changed_files = ("other.yaml",)  # type: ignore[misc]


def test_flow_blocked_optional_fields():
    """Test FlowBlocked event with optional fields."""
    event = FlowBlocked(
        issue_number=1,
        branch="test",
        blocked_reason="test",
        actor="custom:actor",
        timestamp="2026-06-11T00:00:00Z",
    )
    assert event.actor == "custom:actor"
    assert event.timestamp == "2026-06-11T00:00:00Z"


def test_pr_merged_optional_fields():
    """Test PRMerged event with optional fields."""
    event = PRMerged(
        issue_number=1,
        branch="test",
        pr_number=1,
        merged_by="user:alice",
        timestamp="2026-06-11T00:00:00Z",
    )
    assert event.merged_by == "user:alice"
    assert event.timestamp == "2026-06-11T00:00:00Z"


def test_policy_changed_optional_fields():
    """Test PolicyChanged event with optional fields."""
    event = PolicyChanged(
        changed_files=("test.yaml",),
        scope=("global", "project"),
        timestamp="2026-06-11T00:00:00Z",
    )
    assert event.scope == ("global", "project")
    assert event.timestamp == "2026-06-11T00:00:00Z"


def test_flow_lifecycle_re_exports():
    """Test that flow lifecycle events are re-exported correctly."""
    from vibe3.domain.events.flow_lifecycle import (
        FlowBlocked,
        FlowCompleted,
        PRMerged,
    )

    # Import successful if we get here
    assert FlowBlocked is not None
    assert FlowCompleted is not None
    assert PRMerged is not None


def test_policy_re_export():
    """Test that PolicyChanged is re-exported correctly."""
    from vibe3.domain.events.policy import PolicyChanged

    # Import successful if we get here
    assert PolicyChanged is not None


def test_flow_blocked_publish_integration():
    """Test publishing FlowBlocked event via EventPublisher."""
    received_events = []

    def handler(event):  # type: ignore[no-untyped-def]
        received_events.append(event)

    subscribe("FlowBlocked", handler)

    pub = get_publisher()
    event = FlowBlocked(
        issue_number=999,
        branch="test/branch",
        blocked_reason="test reason",
    )
    pub.publish(event)

    assert len(received_events) == 1
    assert received_events[0].issue_number == 999
    assert received_events[0].blocked_reason == "test reason"


def test_flow_completed_publish_integration():
    """Test publishing FlowCompleted event via EventPublisher."""
    received_events = []

    def handler(event):  # type: ignore[no-untyped-def]
        received_events.append(event)

    subscribe("FlowCompleted", handler)

    pub = get_publisher()
    event = FlowCompleted(
        issue_number=888,
        branch="test/branch",
        completed_state="done",
    )
    pub.publish(event)

    assert len(received_events) == 1
    assert received_events[0].issue_number == 888
    assert received_events[0].completed_state == "done"


def test_pr_merged_publish_integration():
    """Test publishing PRMerged event via EventPublisher."""
    received_events = []

    def handler(event):  # type: ignore[no-untyped-def]
        received_events.append(event)

    subscribe("PRMerged", handler)

    pub = get_publisher()
    event = PRMerged(
        issue_number=777,
        branch="test/branch",
        pr_number=42,
        merged_by="user:bob",
    )
    pub.publish(event)

    assert len(received_events) == 1
    assert received_events[0].issue_number == 777
    assert received_events[0].pr_number == 42
    assert received_events[0].merged_by == "user:bob"


def test_policy_changed_publish_integration():
    """Test publishing PolicyChanged event via EventPublisher."""
    received_events = []

    def handler(event):  # type: ignore[no-untyped-def]
        received_events.append(event)

    subscribe("PolicyChanged", handler)

    pub = get_publisher()
    event = PolicyChanged(
        changed_files=("config/policies/test.yaml",),
        scope=("test",),
    )
    pub.publish(event)

    assert len(received_events) == 1
    assert received_events[0].changed_files == ("config/policies/test.yaml",)
    assert received_events[0].scope == ("test",)
