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
