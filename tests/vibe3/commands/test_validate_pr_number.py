"""Tests for PR validation helper function."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.commands.inspect_helpers import validate_pr_number
from vibe3.exceptions import UserError


def test_validate_pr_number_valid_pr():
    """Valid PR number passes validation."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
        client = MagicMock()
        client.get_pr.return_value = MagicMock(number=42, title="Test PR")
        mock_gh.return_value = client

        # Should not raise
        validate_pr_number(42)

        client.get_pr.assert_called_once_with(42)


def test_validate_pr_number_is_issue():
    """Number refers to an issue, not a PR."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
        client = MagicMock()
        client.get_pr.return_value = None  # Not a PR
        client.view_issue.return_value = {  # Is an issue
            "number": 42,
            "title": "Bug report",
        }
        mock_gh.return_value = client

        with pytest.raises(UserError) as exc_info:
            validate_pr_number(42)

        assert "#42 is an issue, not a PR" in str(exc_info.value)
        assert "Bug report" in str(exc_info.value)


def test_validate_pr_number_not_found():
    """Number does not exist as PR or issue."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
        client = MagicMock()
        client.get_pr.return_value = None  # Not a PR
        client.view_issue.return_value = None  # Not an issue
        mock_gh.return_value = client

        with pytest.raises(UserError) as exc_info:
            validate_pr_number(999)

        assert "#999 does not exist" in str(exc_info.value)


def test_validate_pr_number_error_message_format():
    """Error message for issue is user-friendly."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
        client = MagicMock()
        client.get_pr.return_value = None
        client.view_issue.return_value = {
            "number": 123,
            "title": "Feature request: Add dark mode",
        }
        mock_gh.return_value = client

        with pytest.raises(UserError) as exc_info:
            validate_pr_number(123)

        error_msg = str(exc_info.value)
        # Should mention it's an issue
        assert "is an issue, not a PR" in error_msg
        # Should show the issue title
        assert "Feature request: Add dark mode" in error_msg
        # Should suggest correct usage
        assert "vibe inspect pr" in error_msg


def test_validate_pr_number_network_error():
    """Network error is properly reported."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_gh:
        client = MagicMock()
        client.get_pr.return_value = None  # Not a PR
        client.view_issue.return_value = "network_error"  # Network failure
        mock_gh.return_value = client

        with pytest.raises(UserError) as exc_info:
            validate_pr_number(42)

        error_msg = str(exc_info.value)
        # Should mention network error
        assert "network or authentication error" in error_msg
        # Should not claim it doesn't exist
        assert "does not exist" not in error_msg
        # Should suggest checking connection
        assert "check your network connection" in error_msg
