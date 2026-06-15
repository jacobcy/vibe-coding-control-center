"""Tests for DomainEvent to error_log projection boundary."""

import tempfile
from unittest.mock import patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.exceptions import E_ISSUE_FAILED, ErrorSeverity
from vibe3.models import EventPublisher
from vibe3.models.domain_events import DomainEvent, IssueFailed
from vibe3.services.orchestra.error_projection import (
    ERROR_PROJECTION_TABLE,
    build_error_projection_hook,
)
from vibe3.services.orchestra.error_tracking import queries


@pytest.fixture
def temp_db():
    """Create a temporary test database and patch SQLiteClient to use it."""
    db = SQLiteClient(db_path=tempfile.mktemp(suffix=".db"))
    # Clear any existing ErrorTrackingService instances
    from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService

    ErrorTrackingService.clear_instance()
    with patch(
        "vibe3.services.orchestra.error_tracking.service.SQLiteClient", return_value=db
    ):
        yield db
    ErrorTrackingService.clear_instance()


@pytest.fixture
def clean_publisher():
    """Reset EventPublisher before and after each test."""
    EventPublisher.reset()
    yield
    EventPublisher.reset()


class TestErrorProjectionTable:
    """Test ERROR_PROJECTION_TABLE lookup and configuration."""

    def test_issue_failed_in_table(self):
        """IssueFailed is in the projection table."""
        assert IssueFailed in ERROR_PROJECTION_TABLE
        error_code, severity = ERROR_PROJECTION_TABLE[IssueFailed]
        assert error_code == E_ISSUE_FAILED
        assert severity == ErrorSeverity.ERROR

    def test_domain_event_not_in_table(self):
        """Base DomainEvent is not in the projection table."""
        assert DomainEvent not in ERROR_PROJECTION_TABLE


class TestBuildErrorProjectionHook:
    """Test build_error_projection_hook factory function."""

    def test_hook_projects_issue_failed(self, temp_db):
        """IssueFailed is projected to error_log."""
        hook = build_error_projection_hook()

        event = IssueFailed(
            issue_number=123,
            reason="Test failure reason",
            actor="test:actor",
        )

        hook(event)

        # Verify error was recorded
        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 1
        error = errors[0]
        assert error["error_code"] == E_ISSUE_FAILED
        assert error["error_message"] == "Test failure reason"
        assert error["issue_number"] == 123
        assert error["severity"] == "ERROR"

    def test_hook_skips_unknown_events(self, temp_db):
        """Events not in ERROR_PROJECTION_TABLE are silently skipped."""
        hook = build_error_projection_hook()

        # Create a mock event not in the table
        class MockEvent(DomainEvent):
            pass

        event = MockEvent()

        # Should not raise
        hook(event)

        # No errors should be recorded
        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 0

    def test_hook_isolates_errors(self, temp_db):
        """Hook failures don't break the publish chain."""
        publisher = EventPublisher()
        handler_called = []

        def handler(event: DomainEvent) -> None:
            handler_called.append(True)

        publisher.subscribe("IssueFailed", handler)

        # Mock record_error to fail
        with patch(
            "vibe3.services.orchestra.error_tracking.service.ErrorTrackingService.get_instance"
        ) as mock_get_instance:
            mock_service = mock_get_instance.return_value
            mock_service.record_error.side_effect = RuntimeError("DB error")

            publisher.add_publish_hook(build_error_projection_hook())

            event = IssueFailed(issue_number=456, reason="Test")

            # Should not raise
            publisher.publish(event)

        # Handler should still have been called
        assert handler_called, "Handler should run despite hook error"


class TestPublishIntegration:
    """Test full integration: publish(event) → error_log record."""

    def test_publish_issue_failed_creates_error_log_record(
        self, temp_db, clean_publisher
    ):
        """Publishing IssueFailed creates an error_log record."""
        publisher = EventPublisher()

        # Register projection hook
        publisher.add_publish_hook(build_error_projection_hook())

        # Publish IssueFailed
        event = IssueFailed(
            issue_number=999,
            reason="Integration test failure",
            actor="integration:test",
        )
        publisher.publish(event)

        # Verify projection
        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 1
        assert errors[0]["error_code"] == E_ISSUE_FAILED
        assert errors[0]["error_message"] == "Integration test failure"
        assert errors[0]["issue_number"] == 999
        assert errors[0]["severity"] == "ERROR"

    def test_publish_unknown_event_no_error_log_record(self, temp_db, clean_publisher):
        """Publishing unknown event does not create error_log record."""
        publisher = EventPublisher()
        publisher.add_publish_hook(build_error_projection_hook())

        class UnknownEvent(DomainEvent):
            pass

        event = UnknownEvent()
        publisher.publish(event)

        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 0


class TestProjectionFields:
    """Test that projected fields are correct."""

    def test_issue_failed_has_correct_fields(self, temp_db):
        """IssueFailed projection has all expected fields."""
        hook = build_error_projection_hook()

        event = IssueFailed(
            issue_number=42,
            reason="Test error message",
            actor="custom:actor",
            role="executor",
        )

        hook(event)

        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 1

        error = errors[0]
        assert error["error_code"] == E_ISSUE_FAILED
        assert error["error_message"] == "Test error message"
        assert error["issue_number"] == 42
        assert error["severity"] == "ERROR"

    def test_issue_failed_with_minimal_fields(self, temp_db):
        """IssueFailed with minimal fields uses defaults."""
        hook = build_error_projection_hook()

        event = IssueFailed(issue_number=99, reason="Minimal test")

        hook(event)

        errors = queries.get_recent_errors(temp_db.db_path, limit=10)
        assert len(errors) == 1

        error = errors[0]
        assert error["error_code"] == E_ISSUE_FAILED
        assert error["error_message"] == "Minimal test"
        assert error["issue_number"] == 99
