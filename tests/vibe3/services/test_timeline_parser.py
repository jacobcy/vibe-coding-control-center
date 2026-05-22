"""Tests for timeline_parser service."""

from vibe3.services.timeline_parser import parse_timeline_from_comments


def test_parse_timeline_from_comments_empty():
    """Empty comments should return empty timeline."""
    result = parse_timeline_from_comments([])
    assert result == []


def test_parse_timeline_from_comments_extracts_events():
    """Should extract timeline events from GitHub comments."""
    comments = [
        {
            "author": {"login": "claude-sonnet-4.5"},
            "body": "### flow_created\n\nFlow 'issue-123' created",
            "created_at": "2026-05-22T10:00:00Z",
        },
        {
            "author": {"login": "human-user"},
            "body": "Regular comment",
            "created_at": "2026-05-22T10:05:00Z",
        },
        {
            "author": {"login": "claude-sonnet-4.5"},
            "body": "### state_transitioned\n\nState changed: ready -> claimed",
            "created_at": "2026-05-22T10:10:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should extract 2 events (flow_created, state_transitioned)
    assert len(result) == 2
    assert result[0].event_type == "flow_created"
    assert result[0].actor == "claude-sonnet-4.5"
    assert result[1].event_type == "state_transitioned"


def test_parse_timeline_from_comments_handles_missing_fields():
    """Should handle comments with missing fields gracefully."""
    comments = [
        {
            "author": {},
            "body": "### test_event\n\nTest detail",
            "created_at": "",
        },
        {
            "author": {"login": "test-user"},
            "body": "Regular comment without marker",
            "created_at": "2026-05-22T10:00:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should extract 1 event (test_event)
    assert len(result) == 1
    assert result[0].event_type == "test_event"
    assert result[0].actor == "unknown"


def test_parse_timeline_from_comments_sorts_by_timestamp():
    """Should sort events by timestamp."""
    comments = [
        {
            "author": {"login": "user1"},
            "body": "### event_b\n\nLater event",
            "created_at": "2026-05-22T10:10:00Z",
        },
        {
            "author": {"login": "user2"},
            "body": "### event_a\n\nEarlier event",
            "created_at": "2026-05-22T10:00:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should be sorted by timestamp
    assert len(result) == 2
    assert result[0].event_type == "event_a"
    assert result[1].event_type == "event_b"
