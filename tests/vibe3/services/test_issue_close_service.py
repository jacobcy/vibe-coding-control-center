"""Tests for issue close service."""

from unittest.mock import patch

import pytest

from vibe3.clients.github_client import GitHubClient
from vibe3.services.issue_close_service import IssueCloseService


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def issue_close_service(github_client: GitHubClient) -> IssueCloseService:
    """Create issue close service fixture."""
    return IssueCloseService(github=github_client, repo=None)


def test_close_issue_calls_github_close_once(
    issue_close_service: IssueCloseService,
) -> None:
    """Close issue should call GitHub close_issue once."""
    with patch.object(
        issue_close_service._github, "close_issue", return_value=True
    ) as mock_close:
        result = issue_close_service.close_issue(
            issue_number=123, closing_comment="Task not suitable for execution"
        )

        mock_close.assert_called_once_with(
            issue_number=123, comment="Task not suitable for execution", repo=None
        )
        assert result == "closed"


def test_close_issue_returns_failure_when_close_fails(
    issue_close_service: IssueCloseService,
) -> None:
    """Close issue should return failure when GitHub close fails."""
    with patch.object(
        issue_close_service._github, "close_issue", return_value=False
    ) as mock_close:
        result = issue_close_service.close_issue(
            issue_number=123, closing_comment="Closing comment"
        )

        mock_close.assert_called_once()
        assert result == "failed"


def test_close_issue_passes_closing_comment(
    issue_close_service: IssueCloseService,
) -> None:
    """Close issue should pass closing comment to GitHub client."""
    closing_comment = "This task is deprecated and should not be executed"
    with patch.object(
        issue_close_service._github, "close_issue", return_value=True
    ) as mock_close:
        result = issue_close_service.close_issue(
            issue_number=456, closing_comment=closing_comment
        )

        mock_close.assert_called_once_with(
            issue_number=456, comment=closing_comment, repo=None
        )
        assert result == "closed"


def test_close_issue_without_comment(
    issue_close_service: IssueCloseService,
) -> None:
    """Close issue without comment should still work."""
    with patch.object(
        issue_close_service._github, "close_issue", return_value=True
    ) as mock_close:
        result = issue_close_service.close_issue(issue_number=789)

        mock_close.assert_called_once_with(issue_number=789, comment=None, repo=None)
        assert result == "closed"
