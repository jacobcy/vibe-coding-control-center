"""Tests for timeline_parser service."""

from datetime import datetime

from vibe3.services.shared.timeline import parse_timeline_from_comments


def test_parse_timeline_from_comments_empty():
    """Empty comments should return empty timeline."""
    result = parse_timeline_from_comments([])
    assert result == []


def test_parse_timeline_from_comments_extracts_events():
    """Should extract timeline events from GitHub comments."""
    comments = [
        {
            "author": {"login": "claude-sonnet-4.5"},
            "body": "[flow] Flow blocked\n\nDependency #456 not ready",
            "createdAt": "2026-05-22T10:00:00Z",
        },
        {
            "author": {"login": "human-user"},
            "body": "Regular comment",
            "createdAt": "2026-05-22T10:05:00Z",
        },
        {
            "author": {"login": "claude-sonnet-4.5"},
            "body": "[flow] State transitioned\n\nready -> claimed",
            "createdAt": "2026-05-22T10:10:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should extract 2 events (flow_blocked, state_transitioned)
    assert len(result) == 2
    assert result[0].event_type == "flow_blocked"
    assert result[0].actor == "claude-sonnet-4.5"
    assert result[0].detail == "Dependency #456 not ready"
    assert result[1].event_type == "state_transitioned"


def test_parse_timeline_from_comments_handles_missing_fields():
    """Should handle comments with missing fields gracefully."""
    comments = [
        {
            "author": {},
            "body": "[flow] Flow resumed\n\nTest detail",
            "createdAt": "",
        },
        {
            "author": {"login": "test-user"},
            "body": "Regular comment without marker",
            "createdAt": "2026-05-22T10:00:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should extract 1 event (resumed)
    assert len(result) == 1
    assert result[0].event_type == "resumed"
    assert result[0].actor == "unknown"
    assert result[0].timestamp == datetime.min.isoformat()


def test_parse_timeline_from_comments_sorts_by_timestamp():
    """Should sort events by timestamp."""
    comments = [
        {
            "author": {"login": "user1"},
            "body": "[flow] Flow aborted\n\nLater event",
            "createdAt": "2026-05-22T10:10:00Z",
        },
        {
            "author": {"login": "user2"},
            "body": "[flow] Flow failed\n\nEarlier event",
            "createdAt": "2026-05-22T10:00:00Z",
        },
    ]

    result = parse_timeline_from_comments(comments)

    # Should be sorted by timestamp
    assert len(result) == 2
    assert result[0].event_type == "flow_failed"
    assert result[1].event_type == "flow_aborted"
