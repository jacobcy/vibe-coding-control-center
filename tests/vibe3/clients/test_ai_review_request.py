"""Tests for AI review request functionality via GitHubClient."""

from unittest.mock import MagicMock

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_comment_ops import _generate_ai_review_mention_body


def test_generate_mention_body():
    """Test mention comment body generation."""
    body = _generate_ai_review_mention_body(["codex", "copilot"])

    expected = """@codex
@copilot

Please review changes and fix bugs.
Focus on code quality, test coverage, and potential issues."""
    assert body == expected


def test_generate_mention_body_single_reviewer():
    """Test mention comment body with single reviewer."""
    body = _generate_ai_review_mention_body(["claude"])

    expected = """@claude

Please review changes and fix bugs.
Focus on code quality, test coverage, and potential issues."""
    assert body == expected


def test_request_ai_review_sends_comment():
    """Test review request sends GitHub comment."""
    gh_client = GitHubClient()
    gh_client.create_pr_comment = MagicMock(  # type: ignore[method-assign]
        return_value="https://github.com/comment/123"
    )

    result = gh_client.request_ai_review(42, ["codex", "copilot"])

    assert result == "https://github.com/comment/123"
    gh_client.create_pr_comment.assert_called_once()
    call_args = gh_client.create_pr_comment.call_args
    assert call_args[0][0] == 42  # pr_number
    assert "@codex" in call_args[0][1]  # body
    assert "@copilot" in call_args[0][1]


def test_request_ai_review_returns_none_on_empty_reviewers():
    """Test review request returns None when no reviewers specified."""
    gh_client = GitHubClient()
    gh_client.create_pr_comment = MagicMock()  # type: ignore[method-assign]

    result = gh_client.request_ai_review(42, [])

    assert result is None
    gh_client.create_pr_comment.assert_not_called()


def test_request_ai_review_handles_exception():
    """Test review request handles GitHub API errors gracefully."""
    gh_client = GitHubClient()
    gh_client.create_pr_comment = MagicMock(  # type: ignore[method-assign]
        side_effect=Exception("API error")
    )

    result = gh_client.request_ai_review(42, ["codex"])

    assert result is None
