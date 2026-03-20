"""Unit tests for commit-related helper functions.

Tests focus on _get_recent_commits and _get_pr_commit_count with mocked dependencies.
"""

from unittest.mock import MagicMock, patch

from vibe3.commands.inspect_helpers import (
    _get_pr_commit_count,
    _get_recent_commits,
)
from vibe3.exceptions import GitError

# ========== _get_recent_commits Tests ==========


def test_get_recent_commits_success():
    """Successfully get recent commits."""
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_github_client,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        # Mock get_pr_commits
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = [
            "abc123",
            "def456",
            "ghi789",
        ]
        mock_github_client.return_value = mock_gh

        # Mock get_commit_message
        mock_get_commit_message.side_effect = [
            "Add feature X",
            "Fix bug Y",
            "update docs",
        ]

        result = _get_recent_commits(42, limit=3)

        assert len(result) == 3
        assert result[0]["sha"] == "abc123"
        assert result[0]["message"] == "Add feature X"
        assert result[1]["sha"] == "def456"
        assert result[2]["sha"] == "ghi789"


def test_get_recent_commits_limit():
    """Respect limit parameter."""
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_github_client,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = ["a", "b", "c", "d", "e", "f"]
        mock_github_client.return_value = mock_gh
        mock_get_commit_message.return_value = "message"
        result = _get_recent_commits(42, limit=3)
        assert len(result) == 3


def test_get_recent_commits_empty():
    """Handle empty commits list."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_github_client:
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = []
        mock_github_client.return_value = mock_gh
        result = _get_recent_commits(42)
        assert result == []


def test_get_recent_commits_github_error():
    """Handle GitHub API error gracefully."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_github_client:
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.side_effect = Exception("API error")
        mock_github_client.return_value = mock_gh
        result = _get_recent_commits(42)
        assert result == []


def test_get_recent_commits_git_error():
    """Skip commits with git errors, continue with others."""
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_github_client,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = ["abc123", "def456", "ghi789"]
        mock_github_client.return_value = mock_gh
        # Second commit fails
        mock_get_commit_message.side_effect = [
            "Add feature X",
            GitError(operation="log", details="Not found"),
            "Update docs",
        ]
        result = _get_recent_commits(42)
        # Should skip failed commit
        assert len(result) == 2
        assert result[0]["sha"] == "abc123"
        assert result[1]["sha"] == "ghi789"


def test_get_recent_commits_short_sha():
    """SHA is shortened to 7 characters."""
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_github_client,
        patch("vibe3.utils.git_helpers.get_commit_message") as mock_get_commit_message,
    ):
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = ["abcdefghijklmnopqrstuvwxyz123456"]
        mock_github_client.return_value = mock_gh
        mock_get_commit_message.return_value = "message"
        result = _get_recent_commits(42)
        assert result[0]["sha"] == "abcdefg"  # First 7 chars


# ========== _get_pr_commit_count Tests ==========


def test_get_pr_commit_count_success():
    """Get commit count successfully."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_github_client:
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = ["a", "b", "c", "d", "e"]
        mock_github_client.return_value = mock_gh
        result = _get_pr_commit_count(42)
        assert result == 5


def test_get_pr_commit_count_empty():
    """Handle empty commits."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_github_client:
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.return_value = []
        mock_github_client.return_value = mock_gh
        result = _get_pr_commit_count(42)
        assert result == 0


def test_get_pr_commit_count_error():
    """Return 0 on error."""
    with patch("vibe3.clients.github_client.GitHubClient") as mock_github_client:
        mock_gh = MagicMock()
        mock_gh.get_pr_commits.side_effect = Exception("API error")
        mock_github_client.return_value = mock_gh
        result = _get_pr_commit_count(42)
        assert result == 0
