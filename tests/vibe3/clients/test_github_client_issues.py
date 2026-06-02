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


def test_remove_assignees_success():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.remove_assignees(1, ["alice", "bob"]) is True

        args = mock_run.call_args[0][0]
        assert "--remove-assignee" in args
        assert "alice" in args
        assert "bob" in args


def test_remove_assignees_empty_is_noop():
    client = _client()
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        assert client.remove_assignees(1, []) is True
        mock_run.assert_not_called()


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


def test_close_issue_if_open_already_closed(github_client: GitHubClient) -> None:
    """Issue already closed should return 'already_closed' without calling close."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "closed"}),
        patch.object(github_client, "close_issue") as mock_close,
    ):
        result = github_client.close_issue_if_open(issue_number=123)

        mock_close.assert_not_called()
        assert result == "already_closed"


def test_close_issue_if_open_calls_close_once(github_client: GitHubClient) -> None:
    """Open issue should call close_issue once and return 'closed'."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(
            issue_number=123, closing_comment="Task not suitable"
        )

        mock_close.assert_called_once_with(
            issue_number=123, comment="Task not suitable", repo=None
        )
        assert result == "closed"


def test_close_issue_if_open_returns_failure_when_close_fails(
    github_client: GitHubClient,
) -> None:
    """Failed close operation should return 'failed'."""
    with (
        patch.object(github_client, "view_issue", return_value={"state": "open"}),
        patch.object(github_client, "close_issue", return_value=False),
    ):
        result = github_client.close_issue_if_open(issue_number=123)

        assert result == "failed"


def test_create_issue_success(github_client: GitHubClient) -> None:
    """create_issue should return issue number on success."""
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        # Mock gh issue create output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/42\n",
        )

        result = github_client.create_issue(
            title="Test Issue",
            body="Test body",
        )

        assert result == 42
        mock_run.assert_called_once()


def test_create_issue_with_labels(github_client: GitHubClient) -> None:
    """create_issue should apply labels when provided."""
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/43\n",
        )

        result = github_client.create_issue(
            title="Labeled Issue",
            body="Body",
            labels=["bug", "state/ready"],
        )

        assert result == 43
        args = mock_run.call_args[0][0]
        assert "--label" in args
        assert "bug" in args
        assert "state/ready" in args


def test_create_issue_with_repo_override(github_client: GitHubClient) -> None:
    """create_issue should pass --repo flag when repo is provided."""
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/org/repo/issues/44\n",
        )

        result = github_client.create_issue(
            title="Cross-repo Issue",
            body="Body",
            repo="org/repo",
        )

        assert result == 44
        args = mock_run.call_args[0][0]
        assert "--repo" in args
        assert "org/repo" in args


def test_create_issue_failure_returns_none(github_client: GitHubClient) -> None:
    """create_issue should return None on failure."""
    with patch("vibe3.clients.github_issue_admin_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Validation Failed",
        )

        result = github_client.create_issue(
            title="Invalid Issue",
            body="Body",
        )

        assert result is None


def test_list_issue_comments_success(github_client: GitHubClient) -> None:
    """list_issue_comments should return comments on success."""
    with patch("vibe3.clients.github_issues_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "comments": [
                        {
                            "id": 1,
                            "body": "First comment",
                            "author": {"login": "user1"},
                        },
                        {
                            "id": 2,
                            "body": "Second comment",
                            "author": {"login": "user2"},
                        },
                    ]
                }
            ),
        )

        comments = github_client.list_issue_comments(issue_number=42)

        assert len(comments) == 2
        assert comments[0]["id"] == 1
        assert comments[0]["body"] == "First comment"
        assert comments[1]["id"] == 2


def test_list_issue_comments_failure_returns_empty(github_client: GitHubClient) -> None:
    """list_issue_comments should return empty list on failure."""
    with patch("vibe3.clients.github_issues_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Issue not found",
        )

        comments = github_client.list_issue_comments(issue_number=999)

        assert comments == []


def test_list_issue_comments_passes_repo(github_client: GitHubClient) -> None:
    """list_issue_comments should pass repo override to gh CLI."""
    with patch("vibe3.clients.github_issues_ops.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"comments": []}),
        )

        github_client.list_issue_comments(issue_number=42, repo="org/repo")

        # Verify gh issue view was called with the correct repo
        args = mock_run.call_args[0][0]
        assert "--repo" in args
        assert "org/repo" in args


def test_list_issue_comments_timeout_returns_empty(github_client: GitHubClient) -> None:
    """list_issue_comments should return empty list on timeout."""
    import subprocess

    with patch("vibe3.clients.github_issues_ops.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        comments = github_client.list_issue_comments(issue_number=42)

        assert comments == []
