"""Tests for HandoffService external event recording."""

from unittest.mock import MagicMock

import pytest

from vibe3.services.handoff_service import HandoffService


@pytest.fixture
def handoff_svc() -> HandoffService:
    """Create HandoffService with mocked dependencies."""
    store = MagicMock()
    git_client = MagicMock()
    git_client.get_current_branch.return_value = "test-branch"
    return HandoffService(store=store, git_client=git_client)


class TestRecordCIStatus:
    """Tests for record_ci_status method."""

    def test_record_ci_status_no_previous_event(
        self, handoff_svc: HandoffService
    ) -> None:
        """Should record CI status when no previous event exists."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        result = handoff_svc.record_ci_status(
            branch="test-branch",
            pr_number=123,
            status="SUCCESS",
        )

        assert result is True
        handoff_svc.store.add_event.assert_called_once()
        call_args = handoff_svc.store.add_event.call_args
        assert call_args[0][0] == "test-branch"
        assert call_args[0][1] == "handoff_ci_status"
        assert call_args[0][2] == "system/github"
        assert "SUCCESS" in call_args[1]["detail"]
        assert call_args[1]["refs"]["status"] == "SUCCESS"
        assert call_args[1]["refs"]["pr_number"] == "123"

    def test_record_ci_status_changed(self, handoff_svc: HandoffService) -> None:
        """Should record CI status when status changed."""
        last_event = MagicMock()
        last_event.refs = {"status": "PENDING"}
        handoff_svc.get_handoff_events = MagicMock(return_value=[last_event])

        result = handoff_svc.record_ci_status(
            branch="test-branch",
            pr_number=123,
            status="SUCCESS",
        )

        assert result is True
        handoff_svc.store.add_event.assert_called_once()

    def test_record_ci_status_unchanged(self, handoff_svc: HandoffService) -> None:
        """Should not record CI status when status unchanged."""
        last_event = MagicMock()
        last_event.refs = {"status": "SUCCESS"}
        handoff_svc.get_handoff_events = MagicMock(return_value=[last_event])

        result = handoff_svc.record_ci_status(
            branch="test-branch",
            pr_number=123,
            status="SUCCESS",
        )

        assert result is False
        handoff_svc.store.add_event.assert_not_called()

    def test_record_ci_status_custom_actor(self, handoff_svc: HandoffService) -> None:
        """Should use custom actor when provided."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        handoff_svc.record_ci_status(
            branch="test-branch",
            pr_number=123,
            status="FAILURE",
            actor="custom/actor",
        )

        call_args = handoff_svc.store.add_event.call_args
        assert call_args[0][2] == "custom/actor"


class TestRecordPRComments:
    """Tests for record_pr_comments method."""

    def test_record_pr_comments_new_comments(self, handoff_svc: HandoffService) -> None:
        """Should record new comments."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        comments = [
            {"id": 1, "author": {"login": "user1"}, "body": "Comment 1"},
            {"id": 2, "author": {"login": "user2"}, "body": "Comment 2"},
        ]

        result = handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=comments,
        )

        assert result == 2
        assert handoff_svc.store.add_event.call_count == 2

    def test_record_pr_comments_skip_duplicates(
        self, handoff_svc: HandoffService
    ) -> None:
        """Should skip comments already recorded."""
        existing_event = MagicMock()
        existing_event.refs = {"comment_id": "1"}
        handoff_svc.get_handoff_events = MagicMock(return_value=[existing_event])

        comments = [
            {"id": 1, "author": {"login": "user1"}, "body": "Already recorded"},
            {"id": 2, "author": {"login": "user2"}, "body": "New comment"},
        ]

        result = handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=comments,
        )

        assert result == 1
        handoff_svc.store.add_event.assert_called_once()
        call_args = handoff_svc.store.add_event.call_args
        assert call_args[1]["refs"]["comment_id"] == "2"

    def test_record_pr_comments_with_review_comments(
        self, handoff_svc: HandoffService
    ) -> None:
        """Should handle both general and review comments."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        comments = [{"id": 1, "author": {"login": "user1"}, "body": "General"}]
        review_comments = [{"id": 2, "author": {"login": "user2"}, "body": "Review"}]

        result = handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=comments,
            review_comments=review_comments,
        )

        assert result == 2
        assert handoff_svc.store.add_event.call_count == 2

        # Check that both comment types were recorded
        calls = handoff_svc.store.add_event.call_args_list
        comment_types = [call[1]["refs"]["comment_type"] for call in calls]
        assert "general" in comment_types
        assert "review" in comment_types

    def test_record_pr_comments_empty_lists(self, handoff_svc: HandoffService) -> None:
        """Should handle empty comment lists."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        result = handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=[],
            review_comments=[],
        )

        assert result == 0
        handoff_svc.store.add_event.assert_not_called()

    def test_record_pr_comments_truncate_long_body(
        self, handoff_svc: HandoffService
    ) -> None:
        """Should truncate comment body to 200 characters."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        long_body = "x" * 300
        comments = [{"id": 1, "author": {"login": "user1"}, "body": long_body}]

        handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=comments,
        )

        call_args = handoff_svc.store.add_event.call_args
        detail = call_args[1]["detail"]
        assert len(detail) < len(long_body) + 50  # Allow for prefix

    def test_record_pr_comments_handles_missing_fields(
        self, handoff_svc: HandoffService
    ) -> None:
        """Should handle comments with missing fields gracefully."""
        handoff_svc.get_handoff_events = MagicMock(return_value=[])

        # Comments with various missing fields
        comments = [
            {"id": 1},  # Missing author and body
            {
                "number": 2,
                "author": {"login": "user1"},
            },  # Missing body, uses 'number' field
        ]

        result = handoff_svc.record_pr_comments(
            branch="test-branch",
            pr_number=123,
            comments=comments,
        )

        assert result == 2
        assert handoff_svc.store.add_event.call_count == 2
