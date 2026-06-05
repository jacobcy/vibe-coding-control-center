"""Tests for issue body operations."""

import json
from unittest.mock import MagicMock, patch

from vibe3.clients.github_client_base import GitHubClientBase
from vibe3.clients.github_issue_body_ops import IssueBodyMixin


class _TestIssueBodyOps(GitHubClientBase, IssueBodyMixin):
    """Test class for mixin."""


def test_get_issue_body_success() -> None:
    """Test successful body retrieval."""
    ops = _TestIssueBodyOps()

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"body": "Test issue body"}),
        )
        body = ops.get_issue_body(123)
        assert body == "Test issue body"


def test_get_issue_body_not_found() -> None:
    """Test body retrieval failure."""
    ops = _TestIssueBodyOps()

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="issue not found",
        )
        body = ops.get_issue_body(999)
        assert body is None


def test_update_issue_body_success() -> None:
    """Test successful body update."""
    ops = _TestIssueBodyOps()

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = ops.update_issue_body(123, "New body")
        assert result is True


def test_update_issue_body_failure() -> None:
    """Test body update failure."""
    ops = _TestIssueBodyOps()

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="permission denied",
        )
        result = ops.update_issue_body(123, "New body")
        assert result is False
