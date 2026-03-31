"""Tests for GitHub client - Issues."""

import json
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_client import GitHubClient


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess.run."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock:
        yield mock


def _client() -> GitHubClient:
    return GitHubClient()


def test_list_issues_with_assignees_success():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "number": 1,
                        "title": "Test Issue",
                        "assignees": [{"login": "user1"}],
                        "labels": [{"name": "bug"}],
                    }
                ]
            ),
        )

        issues = client.list_issues_with_assignees()
        assert len(issues) == 1
        assert issues[0]["number"] == 1
        assert issues[0]["assignees"][0]["login"] == "user1"


def test_list_issues_with_assignees_failure_returns_empty():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        issues = client.list_issues_with_assignees()
        assert issues == []


def test_list_issues_with_assignees_passes_repo():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        client.list_issues_with_assignees(repo="org/repo")

        # Verify gh issue list was called with the correct repo
        found_repo = False
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "--repo" in args and "org/repo" in args:
                found_repo = True
        assert found_repo


def test_close_issue_success():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.close_issue(1) is True


def test_close_issue_with_comment():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.close_issue(1, comment="Fixed it") is True


def test_close_issue_failure_returns_false():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert client.close_issue(1) is False


def test_add_comment_success():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.add_comment(1, "Nice") is True


def test_add_comment_failure_returns_false():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert client.add_comment(1, "Nice") is False


def test_add_comment_passes_repo():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        client.add_comment(1, "Nice", repo="org/repo")

        # Verify gh issue comment was called with the correct repo
        found_repo = False
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "--repo" in args and "org/repo" in args:
                found_repo = True
        assert found_repo


def test_get_pr_for_issue_found():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "number": 123,
                        "closingIssuesReferences": [{"number": 1}],
                    }
                ]
            ),
        )
        assert client.get_pr_for_issue(1) == 123


def test_get_pr_for_issue_not_found():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
        )
        assert client.get_pr_for_issue(1) is None


def test_get_pr_for_issue_gh_failure():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        assert client.get_pr_for_issue(1) is None
