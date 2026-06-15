"""Tests for DomainEvent to FlowEvent projection boundary."""

import tempfile
from unittest.mock import patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.models import EventPublisher
from vibe3.models.domain_events import (
    DomainEvent,
    ExecutorDispatchIntent,
    FlowBlocked,
    FlowCompleted,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
    PRMerged,
    ReviewerDispatchIntent,
)
from vibe3.services.flow.event_projection import (
    PROJECTION_TABLE,
    build_event_projection_hook,
    project_domain_event,
)


@pytest.fixture
def temp_db():
    """Create a temporary test database and patch SQLiteClient to use it."""
    db = SQLiteClient(db_path=tempfile.mktemp(suffix=".db"))
    with patch("vibe3.services.flow.event_projection.SQLiteClient", return_value=db):
        yield db


@pytest.fixture
def clean_publisher():
    """Reset EventPublisher before and after each test."""
    EventPublisher.reset()
    yield
    EventPublisher.reset()


class TestProjectionTable:
    """Test projection table lookup and configuration."""

    def test_flow_completed_in_table(self):
        """FlowCompleted is in the projection table."""
        assert FlowCompleted in PROJECTION_TABLE
        assert PROJECTION_TABLE[FlowCompleted] == "flow_completed"

    def test_pr_merged_in_table(self):
        """PRMerged is in the projection table."""
        assert PRMerged in PROJECTION_TABLE
        assert PROJECTION_TABLE[PRMerged] == "pr_merged"

    def test_flow_blocked_in_table(self):
        """FlowBlocked is in the projection table."""
        assert FlowBlocked in PROJECTION_TABLE
        assert PROJECTION_TABLE[FlowBlocked] == "flow_blocked"

    def test_dispatch_intents_not_in_table(self):
        """Dispatch intent events are not in the projection table."""
        assert ManagerDispatchIntent not in PROJECTION_TABLE
        assert PlannerDispatchIntent not in PROJECTION_TABLE
        assert ExecutorDispatchIntent not in PROJECTION_TABLE
        assert ReviewerDispatchIntent not in PROJECTION_TABLE


class TestProjectDomainEvent:
    """Test project_domain_event core function."""

    def test_known_event_projects(self, temp_db):
        """FlowCompleted is projected to flow_events."""
        event = FlowCompleted(
            issue_number=123,
            branch="task/issue-123-test",
            completed_state="done",
            actor="test:actor",
        )

        result = project_domain_event(event)

        assert result is True

        events = temp_db.get_events(branch="task/issue-123-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "flow_completed"
        assert events[0]["branch"] == "task/issue-123-test"
        assert events[0]["actor"] == "test:actor"
        assert "completed_state=done" in events[0]["detail"]
        assert "issue_number=123" in events[0]["detail"]
        assert events[0]["refs"] == {"issue_number": 123}

    def test_pr_merged_projects(self, temp_db):
        """PRMerged is projected to flow_events."""
        event = PRMerged(
            issue_number=100,
            branch="task/issue-100-test",
            pr_number=42,
            merged_by="user:test",
            actor="system:check",
        )

        result = project_domain_event(event)

        assert result is True

        events = temp_db.get_events(branch="task/issue-100-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "pr_merged"
        assert events[0]["branch"] == "task/issue-100-test"
        assert events[0]["actor"] == "system:check"
        assert "pr_number=42" in events[0]["detail"]
        assert "merged_by=user:test" in events[0]["detail"]
        assert events[0]["refs"] == {"issue_number": 100, "pr_number": 42}

    def test_flow_blocked_projects_correctly(self, temp_db):
        """FlowBlocked is projected to flow_events."""
        event = FlowBlocked(
            issue_number=456,
            branch="task/issue-456-test",
            blocked_reason="test blocker",
            actor="test:actor",
        )

        result = project_domain_event(event)

        assert result is True

        events = temp_db.get_events(branch="task/issue-456-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "flow_blocked"
        assert events[0]["branch"] == "task/issue-456-test"
        assert events[0]["actor"] == "test:actor"
        assert "blocked_reason=test blocker" in events[0]["detail"]
        assert "issue_number=456" in events[0]["detail"]
        assert events[0]["refs"] == {"issue_number": 456}

    def test_unknown_event_not_projected(self, temp_db):
        """Event not in projection table is not projected."""
        event = ManagerDispatchIntent(
            issue_number=456,
            branch="task/issue-456-test",
            trigger_state="ready",
        )

        result = project_domain_event(event)

        assert result is False

        events = temp_db.get_events(branch="task/issue-456-test")
        assert len(events) == 0

    def test_dispatch_intent_not_projected(self, temp_db):
        """ManagerDispatchIntent is not projected."""
        event = ManagerDispatchIntent(
            issue_number=789,
            branch="task/issue-789-test",
            trigger_state="ready",
        )

        result = project_domain_event(event)

        assert result is False

        events = temp_db.get_events(branch="task/issue-789-test")
        assert len(events) == 0


class TestPublishIntegration:
    """Test full integration: publish(event) → projected record."""

    def test_publish_flow_completed_creates_timeline_record(
        self, temp_db, clean_publisher
    ):
        """Publishing FlowCompleted creates a flow_events record."""
        publisher = EventPublisher()

        # Register projection hook
        publisher.add_publish_hook(build_event_projection_hook())

        # Publish FlowCompleted
        event = FlowCompleted(
            issue_number=999,
            branch="task/issue-999-test",
            completed_state="merged",
            actor="integration:test",
        )
        publisher.publish(event)

        # Verify projection
        events = temp_db.get_events(branch="task/issue-999-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "flow_completed"
        assert events[0]["actor"] == "integration:test"

    def test_publish_pr_merged_creates_timeline_record(self, temp_db, clean_publisher):
        """Publishing PRMerged creates a flow_events record."""
        publisher = EventPublisher()

        # Register projection hook
        publisher.add_publish_hook(build_event_projection_hook())

        # Publish PRMerged
        event = PRMerged(
            issue_number=200,
            branch="task/issue-200-test",
            pr_number=55,
            merged_by="user:integration",
        )
        publisher.publish(event)

        # Verify projection
        events = temp_db.get_events(branch="task/issue-200-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "pr_merged"
        assert events[0]["actor"] == "system:check"
        assert "pr_number=55" in events[0]["detail"]
        assert "merged_by=user:integration" in events[0]["detail"]
        assert events[0]["refs"] == {"issue_number": 200, "pr_number": 55}

    def test_publish_flow_blocked_creates_timeline_record(
        self, temp_db, clean_publisher
    ):
        """Publishing FlowBlocked creates a flow_events record."""
        publisher = EventPublisher()

        # Register projection hook
        publisher.add_publish_hook(build_event_projection_hook())

        # Publish FlowBlocked
        event = FlowBlocked(
            issue_number=999,
            branch="task/issue-999-test",
            blocked_reason="test blocker",
            actor="integration:test",
        )
        publisher.publish(event)

        # Verify projection
        events = temp_db.get_events(branch="task/issue-999-test")
        assert len(events) == 1
        assert events[0]["event_type"] == "flow_blocked"
        assert events[0]["actor"] == "integration:test"
        assert "blocked_reason=test blocker" in events[0]["detail"]

    def test_publish_unknown_event_no_timeline_record(self, temp_db, clean_publisher):
        """Publishing unknown event does not create timeline record."""
        publisher = EventPublisher()
        publisher.add_publish_hook(build_event_projection_hook())

        event = ManagerDispatchIntent(
            issue_number=888,
            branch="task/issue-888-test",
            trigger_state="ready",
        )
        publisher.publish(event)

        events = temp_db.get_events(branch="task/issue-888-test")
        assert len(events) == 0


class TestErrorIsolation:
    """Test that projection failures are isolated."""

    def test_projection_error_does_not_break_publish(self, clean_publisher):
        """Projection hook error does not prevent handlers from running."""
        publisher = EventPublisher()
        handler_called = []

        # Register a handler that should still be called
        def handler(event: DomainEvent) -> None:
            handler_called.append(True)

        publisher.subscribe("FlowCompleted", handler)

        # Use a hook that will fail
        def bad_hook(event: DomainEvent) -> None:
            raise RuntimeError("projection failed")

        publisher.add_publish_hook(bad_hook)

        # Publish should not raise
        event = FlowCompleted(
            issue_number=100,
            branch="task/issue-100-test",
            completed_state="done",
        )
        publisher.publish(event)

        # Handler should still have been called
        assert handler_called, "Handler should run despite hook error"

    def test_build_hook_catches_exceptions(self, clean_publisher, temp_db):
        """build_event_projection_hook catches and logs exceptions."""
        publisher = EventPublisher()
        publisher.add_publish_hook(build_event_projection_hook())

        # Create an event that will fail in projection (no branch field)
        # Using a mock event that's in the table but lacks branch
        with patch(
            "vibe3.services.flow.event_projection.PROJECTION_TABLE",
            {DomainEvent: "test_event"},
        ):
            event = DomainEvent()
            # Should not raise, just log
            publisher.publish(event)


class TestProjectionFields:
    """Test that projected fields are correct."""

    def test_flow_completed_has_correct_fields(self, temp_db):
        """FlowCompleted projection has all expected fields."""
        event = FlowCompleted(
            issue_number=42,
            branch="feature/test-branch",
            completed_state="done",
            actor="custom:actor",
        )

        project_domain_event(event)

        events = temp_db.get_events(branch="feature/test-branch")
        assert len(events) == 1

        proj = events[0]
        assert proj["event_type"] == "flow_completed"
        assert proj["branch"] == "feature/test-branch"
        assert proj["actor"] == "custom:actor"
        assert proj["detail"] == "completed_state=done, issue_number=42"
        assert proj["refs"] == {"issue_number": 42}

    def test_default_actor(self, temp_db):
        """FlowCompleted without actor uses default."""
        # Create event without actor (it has default in dataclass)
        event = FlowCompleted(
            issue_number=99,
            branch="task/issue-99",
            completed_state="merged",
        )

        project_domain_event(event)

        events = temp_db.get_events(branch="task/issue-99")
        assert events[0]["actor"] == "system:flow"

    def test_pr_merged_has_correct_fields(self, temp_db):
        """PRMerged projection has all expected fields."""
        event = PRMerged(
            issue_number=42,
            branch="feature/pr-test",
            pr_number=123,
            merged_by="user:alice",
        )

        project_domain_event(event)

        events = temp_db.get_events(branch="feature/pr-test")
        assert len(events) == 1

        proj = events[0]
        assert proj["event_type"] == "pr_merged"
        assert proj["branch"] == "feature/pr-test"
        assert proj["actor"] == "system:check"
        assert "pr_number=123" in proj["detail"]
        assert "merged_by=user:alice" in proj["detail"]
        assert proj["refs"] == {"issue_number": 42, "pr_number": 123}

    def test_pr_merged_without_merged_by(self, temp_db):
        """PRMerged without merged_by still projects correctly."""
        event = PRMerged(
            issue_number=50,
            branch="feature/pr-test-2",
            pr_number=999,
            merged_by=None,  # Explicitly None
        )

        project_domain_event(event)

        events = temp_db.get_events(branch="feature/pr-test-2")
        assert len(events) == 1

        proj = events[0]
        assert proj["event_type"] == "pr_merged"
        assert proj["actor"] == "system:check"
        # merged_by should not appear in detail when None
        assert "pr_number=999" in proj["detail"]
        assert "merged_by" not in proj["detail"]
        assert proj["refs"] == {"issue_number": 50, "pr_number": 999}
