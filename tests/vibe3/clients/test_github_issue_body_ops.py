"""Tests for issue body operations."""

from unittest.mock import MagicMock, patch

from vibe3.clients.github_client_base import GitHubClientBase
from vibe3.clients.github_issue_admin_ops import IssueAdminMixin
from vibe3.clients.github_issues_ops import IssuesMixin


class _TestIssuesOps(GitHubClientBase, IssuesMixin):
    """Test class for IssuesMixin."""

    pass


class _TestAdminOps(GitHubClientBase, IssueAdminMixin):
    """Test class for IssueAdminMixin."""

    pass


def test_get_issue_body_success() -> None:
    """Test successful body retrieval."""
    ops = _TestIssuesOps()

    with patch.object(ops, "view_issue") as mock_view:
        mock_view.return_value = {"body": "Test issue body"}
        body = ops.get_issue_body(123)
        assert body == "Test issue body"
        mock_view.assert_called_once_with(123, repo=None)


def test_get_issue_body_with_repo() -> None:
    """Test body retrieval with repo parameter."""
    ops = _TestIssuesOps()

    with patch.object(ops, "view_issue") as mock_view:
        mock_view.return_value = {"body": "Test issue body"}
        body = ops.get_issue_body(123, repo="owner/repo")
        assert body == "Test issue body"
        mock_view.assert_called_once_with(123, repo="owner/repo")


def test_get_issue_body_not_found() -> None:
    """Test body retrieval when issue not found."""
    ops = _TestIssuesOps()

    with patch.object(ops, "view_issue") as mock_view:
        mock_view.return_value = None
        body = ops.get_issue_body(999)
        assert body is None


def test_get_issue_body_network_error() -> None:
    """Test body retrieval on network error."""
    ops = _TestIssuesOps()

    with patch.object(ops, "view_issue") as mock_view:
        mock_view.return_value = "network_error"
        body = ops.get_issue_body(123)
        assert body is None


def test_get_issue_body_empty_body() -> None:
    """Test body retrieval when body key is missing."""
    ops = _TestIssuesOps()

    with patch.object(ops, "view_issue") as mock_view:
        mock_view.return_value = {"number": 123, "title": "Test"}
        body = ops.get_issue_body(123)
        assert body == ""


def test_update_issue_body_success() -> None:
    """Test successful body update."""
    ops = _TestAdminOps()

    with patch.object(ops, "_run_gh_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = ops.update_issue_body(123, "New body")
        assert result is True
        # Verify command structure
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "gh"
        assert call_args[1] == "issue"
        assert call_args[2] == "edit"
        assert "123" in call_args
        assert "--body" in call_args
        assert "New body" in call_args


def test_update_issue_body_with_repo() -> None:
    """Test body update with repo parameter."""
    ops = _TestAdminOps()

    with patch.object(ops, "_run_gh_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = ops.update_issue_body(123, "New body", repo="owner/repo")
        assert result is True
        # Verify --repo flag is added
        call_args = mock_run.call_args[0][0]
        assert "--repo" in call_args
        assert "owner/repo" in call_args


def test_update_issue_body_failure() -> None:
    """Test body update failure."""
    ops = _TestAdminOps()

    with patch.object(ops, "_run_gh_command") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="permission denied",
        )
        result = ops.update_issue_body(123, "New body")
        assert result is False
