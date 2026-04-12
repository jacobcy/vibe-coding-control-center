"""Tests for reviewer role lifecycle publishing helpers."""

from unittest.mock import patch

from vibe3.domain.events import IssueFailed, ReviewCompleted
from vibe3.domain.publisher import EventPublisher
from vibe3.roles.review import (
    publish_review_command_failure,
    publish_review_command_success,
)


def test_publish_review_command_success_emits_review_completed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_review_command_success(
            issue_number=42,
            branch="task/issue-42",
            verdict="PASS",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, ReviewCompleted)
    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.verdict == "PASS"
    assert event.actor == "agent:review"


def test_publish_review_command_success_skips_without_issue_context() -> None:
    EventPublisher.reset()
    with patch.object(EventPublisher, "publish") as mock_publish:
        publish_review_command_success(
            issue_number=None,
            branch=None,
            verdict="PASS",
        )

    mock_publish.assert_not_called()


def test_publish_review_command_failure_emits_issue_failed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_review_command_failure(
            issue_number=24,
            reason="review parse failed: invalid format",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 24
    assert "invalid format" in event.reason
    assert event.actor == "agent:review"


def test_publish_review_command_failure_skips_without_issue_number() -> None:
    EventPublisher.reset()
    with patch.object(EventPublisher, "publish") as mock_publish:
        publish_review_command_failure(
            issue_number=None,
            reason="ignored",
        )

    mock_publish.assert_not_called()
