"""Tests for FlowTimelineService."""

from unittest.mock import Mock

from vibe3.services.flow.timeline import FlowTimelineService


def test_record_timeline_event_creates_event_and_comment():
    """Test that record_timeline_event calls both add_event and add_comment.

    Uses milestone_recorded event which is allowed by policy (future placeholder).
    """
    mock_store = Mock()
    mock_github = Mock()

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="milestone_recorded",  # Policy allows comment for this
        actor="claude/sonnet-4.6",
        detail="Important milestone reached",
        issue_number=123,
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once_with(
        "dev/issue-123",
        "milestone_recorded",
        "claude/sonnet-4.6",
        "Important milestone reached",
    )

    # Verify comment added
    mock_github.add_comment.assert_called_once()
    call_args = mock_github.add_comment.call_args
    assert call_args[0][0] == 123  # issue_number
    body = call_args[0][1]  # comment body
    assert body.startswith("[flow]")
    assert "milestone" in body.lower()
    assert "recorded" in body.lower()


def test_record_timeline_event_skips_comment_if_no_issue():
    """Test that comment is skipped when issue_number is None."""
    mock_store = Mock()
    mock_github = Mock()

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="state_transitioned",  # Policy allows comment, but no issue_number
        actor="claude/sonnet-4.6",
        detail="Transitioned from ready to claimed",
        issue_number=None,  # No issue
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once()

    # Verify NO comment added
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_dedupe_skips_same_event_type():
    """Test that duplicate event_type comments are skipped.

    Uses milestone_recorded event which is allowed by policy.
    """
    mock_store = Mock()
    mock_github = Mock()

    # Mock existing comments with [flow] milestone_recorded comment
    mock_github.view_issue.return_value = {
        "comments": [
            {"body": "[flow] Milestone recorded\n\nImportant milestone reached"}
        ]
    }

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Try to record another milestone_recorded event
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="milestone_recorded",
        actor="claude/sonnet-4.6",
        detail=("Another milestone reached"),  # Different detail but same event_type
        issue_number=123,
    )

    # Verify event recorded (event always recorded)
    mock_store.add_event.assert_called_once()

    # Verify comment NOT added (dedupe)
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_dedupe_handoff_append():
    """Test that duplicate handoff_append comments are skipped."""
    mock_store = Mock()
    mock_github = Mock()

    # Mock existing comments with [flow] Handoff update comment
    mock_github.view_issue.return_value = {
        "comments": [{"body": "[flow] Handoff update\n\nPR #42 closed"}]
    }

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Try to record another handoff_append event
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="handoff_append",
        actor="claude/sonnet-4.6",
        detail="Another update",  # Different detail but same event_type
        issue_number=123,
    )

    # Verify event recorded (event always recorded)
    mock_store.add_event.assert_called_once()

    # Verify comment NOT added (dedupe)
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_policy_blocks_state_sync_events():
    """Test that policy blocks state_sync events from writing comments.

    flow_blocked, resumed, flow_aborted should NOT write comments.
    """
    mock_store = Mock()
    mock_github = Mock()

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Test flow_blocked (state_sync event)
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="flow_blocked",
        actor="claude/sonnet-4.6",
        detail="Blocked by #456",
        issue_number=123,
    )

    # Verify event recorded (always)
    mock_store.add_event.assert_called_once()

    # Verify NO comment added (policy blocked)
    mock_github.add_comment.assert_not_called()


def test_record_timeline_event_allows_different_event_type():
    """Test that different event_type comments are added.

    Uses milestone_recorded and user_notification which are both allowed by policy.
    """
    mock_store = Mock()
    mock_github = Mock()

    # Mock existing comments with [flow] milestone_recorded comment
    mock_github.view_issue.return_value = {
        "comments": [{"body": "[flow] Milestone recorded\n\nFirst milestone"}]
    }

    service = FlowTimelineService(store=mock_store, github_client=mock_github)

    # Record user_notification event (different event_type)
    service.record_timeline_event(
        branch="dev/issue-123",
        event_type="user_notification",
        actor="claude/sonnet-4.6",
        detail="User notification sent",
        issue_number=123,
    )

    # Verify event recorded
    mock_store.add_event.assert_called_once()

    # Verify comment added (different event_type, no dedupe)
    mock_github.add_comment.assert_called_once()
