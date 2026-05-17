"""Tests for FlowTimelineService."""

from unittest.mock import Mock

from vibe3.services.flow_timeline_service import FlowTimelineService


def test_record_timeline_event_creates_event_and_comment():
    """Test that record_timeline_event calls both add_event and add_comment."""
    mock_store = Mock()
    mock_github = Mock()

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="flow_blocked",
        actor="claude/sonnet-4.6",
        detail="Blocked by #456",
        issue_number=123,
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once_with(
        "dev/issue-123",
        "flow_blocked",
        "claude/sonnet-4.6",
        "Blocked by #456",
    )

    # Verify comment added
    mock_github.add_comment.assert_called_once()
    call_args = mock_github.add_comment.call_args
    assert call_args[0][0] == 123  # issue_number
    body = call_args[0][1]  # comment body
    assert body.startswith("[flow]")
    assert "blocked" in body.lower()
    assert "#456" in body


def test_record_timeline_event_skips_comment_if_no_issue():
    """Test that comment is skipped when issue_number is None."""
    mock_store = Mock()
    mock_github = Mock()

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="flow_blocked",
        actor="claude/sonnet-4.6",
        detail="Blocked by #456",
        issue_number=None,  # No issue
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once()

    # Verify NO comment added
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_dedupe_skips_same_event_type():
    """Test that duplicate event_type comments are skipped."""
    mock_store = Mock()
    mock_github = Mock()

    # Mock existing comments with [flow] blocked comment
    mock_github.view_issue.return_value = {
        "comments": [{"body": "[flow] Flow blocked\n\nBlocked by #456"}]
    }

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Try to record another blocked event
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="flow_blocked",
        actor="claude/sonnet-4.6",
        detail="Blocked by #789",  # Different detail but same event_type
        issue_number=123,
    )

    # Verify event recorded (event always recorded)
    mock_store.add_event.assert_called_once()

    # Verify comment NOT added (dedupe)
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_allows_different_event_type():
    """Test that different event_type comments are added."""
    mock_store = Mock()
    mock_github = Mock()

    # Mock existing comments with [flow] blocked comment
    mock_github.view_issue.return_value = {
        "comments": [{"body": "[flow] Flow blocked\n\nBlocked by #456"}]
    }

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Record resumed event (different event_type)
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="resumed",
        actor="human:resume",
        detail="Resumed by user",
        issue_number=123,
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once()

    # Verify comment added (different event_type, no dedupe)
    mock_github.add_comment.assert_called_once()
