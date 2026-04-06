"""Tests for PR review request service."""

from unittest.mock import MagicMock

from vibe3.services.pr_review_request_service import PRReviewRequestService


def test_generate_mention_body():
    """Test mention comment body generation."""
    gh_client = MagicMock()
    service = PRReviewRequestService(gh_client)

    body = service._generate_mention_body(["codex", "copilot"])

    expected = """@codex
@copilot

Please review changes and fix bugs.
Focus on code quality, test coverage, and potential issues."""
    assert body == expected


def test_generate_mention_body_single_reviewer():
    """Test mention comment body with single reviewer."""
    gh_client = MagicMock()
    service = PRReviewRequestService(gh_client)

    body = service._generate_mention_body(["claude"])

    expected = """@claude

Please review changes and fix bugs.
Focus on code quality, test coverage, and potential issues."""
    assert body == expected


def test_request_review_sends_comment():
    """Test review request sends GitHub comment."""
    gh_client = MagicMock()
    gh_client.create_pr_comment.return_value = "https://github.com/comment/123"

    service = PRReviewRequestService(gh_client)
    result = service.request_review(42, ["codex", "copilot"])

    assert result == "https://github.com/comment/123"
    gh_client.create_pr_comment.assert_called_once()
    call_args = gh_client.create_pr_comment.call_args
    assert call_args[0][0] == 42  # pr_number
    assert "@codex" in call_args[0][1]  # body
    assert "@copilot" in call_args[0][1]


def test_request_review_returns_none_on_empty_reviewers():
    """Test review request returns None when no reviewers specified."""
    gh_client = MagicMock()
    service = PRReviewRequestService(gh_client)

    result = service.request_review(42, [])

    assert result is None
    gh_client.create_pr_comment.assert_not_called()


def test_request_review_handles_exception():
    """Test review request handles GitHub API errors gracefully."""
    gh_client = MagicMock()
    gh_client.create_pr_comment.side_effect = Exception("API error")

    service = PRReviewRequestService(gh_client)
    result = service.request_review(42, ["codex"])

    assert result is None
