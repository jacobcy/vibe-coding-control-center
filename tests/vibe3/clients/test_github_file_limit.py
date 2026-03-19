"""Tests for GitHub API file limit error handling."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_review_ops import ReviewMixin
from vibe3.exceptions import GitHubError, UserError


@pytest.fixture
def review_mixin():
    """Create ReviewMixin instance."""
    return ReviewMixin()


def test_get_pr_diff_file_limit_error(review_mixin):
    """Test that PR diff with >300 files raises UserError."""
    with patch("subprocess.run") as mock_run:
        # Mock subprocess error with file limit message
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "diff", "200"],
            stderr=(
                "could not find pull request diff: HTTP 406: Sorry,"
                " the diff exceeded the maximum number of files (300)."
                " Consider using 'List pull requests files' API"
                " or locally cloning the repository instead."
            ),
        )

        with pytest.raises(UserError) as exc_info:
            review_mixin.get_pr_diff(200)

        error_msg = str(exc_info.value)
        assert "too many files" in error_msg
        assert "GitHub limit: 300" in error_msg
        assert "#200" in error_msg
        assert "vibe inspect branch" in error_msg


def test_get_pr_diff_other_error(review_mixin):
    """Test that other PR diff errors raise GitHubError."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "diff", "200"],
            stderr="Network error",
        )

        with pytest.raises(GitHubError) as exc_info:
            review_mixin.get_pr_diff(200)

        assert exc_info.value.status_code == 1
        assert "Network error" in exc_info.value.message


def test_get_pr_files_file_limit_error(review_mixin):
    """Test that PR files with >300 files raises UserError."""
    with patch("subprocess.run") as mock_run:
        # Mock subprocess error with file limit message
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "diff", "200", "--name-only"],
            stderr=(
                "could not find pull request diff: HTTP 406: Sorry,"
                " the diff exceeded the maximum number of files (300)."
            ),
        )

        with pytest.raises(UserError) as exc_info:
            review_mixin.get_pr_files(200)

        error_msg = str(exc_info.value)
        assert "too many files" in error_msg
        assert "GitHub limit: 300" in error_msg
        assert "#200" in error_msg


def test_get_pr_files_success(review_mixin):
    """Test successful get_pr_files."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "file1.py\nfile2.py\nfile3.py\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = review_mixin.get_pr_files(42)

        assert result == ["file1.py", "file2.py", "file3.py"]


def test_get_pr_files_other_error(review_mixin):
    """Test that other PR files errors raise GitHubError."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "diff", "200", "--name-only"],
            stderr="Authentication failed",
        )

        with pytest.raises(GitHubError) as exc_info:
            review_mixin.get_pr_files(200)

        assert exc_info.value.status_code == 1
        assert "Authentication failed" in exc_info.value.message


def test_error_message_suggests_alternatives(review_mixin):
    """Test that error message suggests alternative approaches."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "diff", "200"],
            stderr="diff exceeded the maximum number of files (300)",
        )

        with pytest.raises(UserError) as exc_info:
            review_mixin.get_pr_diff(200)

        error_msg = str(exc_info.value)
        # Should suggest alternatives
        assert "Alternatives:" in error_msg
        assert "vibe inspect branch" in error_msg
        assert "pull/200/files" in error_msg
