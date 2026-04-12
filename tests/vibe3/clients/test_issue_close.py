"""Tests for issue close functionality via GitHubClient."""

from unittest.mock import patch

import pytest

from vibe3.clients.github_client import GitHubClient


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


def test_close_issue_if_open_calls_close_once(
    github_client: GitHubClient,
) -> None:
    """Close issue should call GitHub close_issue once when issue is open."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(
            issue_number=123, closing_comment="Task not suitable for execution"
        )

        mock_close.assert_called_once_with(
            issue_number=123, comment="Task not suitable for execution", repo=None
        )
        assert result == "closed"


def test_close_issue_if_open_returns_failure_when_close_fails(
    github_client: GitHubClient,
) -> None:
    """Close issue should return failure when GitHub close fails."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=False) as mock_close,
    ):
        result = github_client.close_issue_if_open(
            issue_number=123, closing_comment="Closing comment"
        )

        mock_close.assert_called_once()
        assert result == "failed"


def test_close_issue_if_open_passes_closing_comment(
    github_client: GitHubClient,
) -> None:
    """Close issue should pass closing comment to GitHub client."""
    closing_comment = "This task is deprecated and should not be executed"
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(
            issue_number=456, closing_comment=closing_comment
        )

        mock_close.assert_called_once_with(
            issue_number=456, comment=closing_comment, repo=None
        )
        assert result == "closed"


def test_close_issue_if_open_without_comment(
    github_client: GitHubClient,
) -> None:
    """Close issue without comment should still work."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(issue_number=789)

        mock_close.assert_called_once_with(issue_number=789, comment=None, repo=None)
        assert result == "closed"


def test_close_issue_if_open_already_closed(
    github_client: GitHubClient,
) -> None:
    """Close issue should return already_closed when issue is already closed."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "closed"}),
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(issue_number=123)

        mock_close.assert_not_called()
        assert result == "already_closed"
