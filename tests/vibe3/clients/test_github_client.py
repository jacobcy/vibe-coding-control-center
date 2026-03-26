"""Tests for GitHub client."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import GitHubError, UserError
from vibe3.models.pr import CreatePRRequest, PRState, UpdatePRRequest


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess.run."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock:
        yield mock


def test_check_auth_success(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check success."""
    mock_subprocess.return_value.returncode = 0

    result = github_client.check_auth()

    assert result is True
    mock_subprocess.assert_called_once_with(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
    )


def test_check_auth_failure(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check failure."""
    mock_subprocess.return_value.returncode = 1

    result = github_client.check_auth()

    assert result is False


def test_create_pr_success(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test create PR success."""
    # Mock create PR
    mock_subprocess.return_value.stdout = "https://github.com/org/repo/pull/123\n"
    mock_subprocess.return_value.returncode = 0

    # Mock get_pr

    with patch.object(github_client, "get_pr") as mock_get_pr:
        mock_get_pr.return_value = MagicMock(
            number=123,
            title="Test PR",
            body="Test body",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            url="https://github.com/org/repo/pull/123",
            draft=True,
        )

        request = CreatePRRequest(
            title="Test PR",
            body="Test body",
            head_branch="feature-branch",
            base_branch="main",
            draft=True,
        )

        pr = github_client.create_pr(request)

        assert pr.number == 123
        mock_subprocess.assert_called()


def test_create_pr_maps_recoverable_error_to_user_error(
    github_client: GitHubClient,
) -> None:
    request = CreatePRRequest(
        title="Test PR",
        body="Test body",
        head_branch="feature-branch",
        base_branch="main",
        draft=True,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "create"],
            stderr=(
                'a pull request for branch "feature-branch" into branch '
                '"main" already exists'
            ),
        )

        with pytest.raises(UserError) as exc_info:
            github_client.create_pr(request)

    assert "PR create failed" in str(exc_info.value)
    assert "already exists" in str(exc_info.value)


def test_create_pr_maps_non_recoverable_error_to_github_error(
    github_client: GitHubClient,
) -> None:
    request = CreatePRRequest(
        title="Test PR",
        body="Test body",
        head_branch="feature-branch",
        base_branch="main",
        draft=True,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "create"],
            stderr="GraphQL: Internal server error",
        )

        with pytest.raises(GitHubError) as exc_info:
            github_client.create_pr(request)

    assert exc_info.value.status_code == 1
    assert "gh pr create failed" in exc_info.value.message


def test_get_pr_by_number(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test get PR by number."""
    pr_data = {
        "number": 123,
        "title": "Test PR",
        "body": "Test body",
        "state": "OPEN",
        "headRefName": "feature-branch",
        "baseRefName": "main",
        "url": "https://github.com/org/repo/pull/123",
        "isDraft": False,
        "createdAt": "2026-03-16T10:00:00Z",
        "updatedAt": "2026-03-16T10:00:00Z",
        "mergedAt": None,
    }

    mock_subprocess.return_value.stdout = json.dumps(pr_data)
    mock_subprocess.return_value.returncode = 0

    pr = github_client.get_pr(pr_number=123)

    assert pr is not None
    assert pr.number == 123
    assert pr.title == "Test PR"
    assert pr.head_branch == "feature-branch"


def test_get_pr_not_found(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test get PR not found."""
    mock_subprocess.return_value.returncode = 1

    pr = github_client.get_pr(pr_number=999)

    assert pr is None


def test_mark_ready_success(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test mark PR as ready."""
    mock_subprocess.return_value.returncode = 0

    with patch.object(github_client, "get_pr") as mock_get_pr:
        mock_get_pr.return_value = MagicMock(number=123, draft=False)

        pr = github_client.mark_ready(123)

        assert pr.number == 123
        mock_subprocess.assert_called()


def test_mark_ready_maps_recoverable_error_to_user_error(
    github_client: GitHubClient,
) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "ready", "123"],
            stderr="pull request is already ready for review",
        )

        with pytest.raises(UserError) as exc_info:
            github_client.mark_ready(123)

    assert "PR ready failed" in str(exc_info.value)


def test_close_issue_success(
    github_client: GitHubClient,
) -> None:
    with patch("vibe3.clients.github_issues_ops.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        result = github_client.close_issue(220)

    assert result is True
    mock_run.assert_called_once_with(
        ["gh", "issue", "close", "220"],
        capture_output=True,
        text=True,
    )


def test_merge_pr_maps_non_recoverable_error_to_github_error(
    github_client: GitHubClient,
) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "merge", "123"],
            stderr="GraphQL: Internal server error",
        )

        with pytest.raises(GitHubError) as exc_info:
            github_client.merge_pr(123)

    assert exc_info.value.status_code == 1
    assert "gh pr merge failed" in exc_info.value.message


def test_update_pr_maps_error_to_user_error(github_client: GitHubClient) -> None:
    request = UpdatePRRequest(number=123, title="new title")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "edit", "123"],
            stderr="no pull requests found for branch",
        )

        with pytest.raises(UserError) as exc_info:
            github_client.update_pr(request)

    assert "PR edit failed" in str(exc_info.value)


def test_merge_pr_success(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test merge PR success."""
    mock_subprocess.return_value.returncode = 0

    with patch.object(github_client, "get_pr") as mock_get_pr:
        mock_get_pr.return_value = MagicMock(number=123)

        pr = github_client.merge_pr(123)

        assert pr.number == 123
        mock_subprocess.assert_called()


def test_extract_pr_number(github_client: GitHubClient) -> None:
    """Test extract PR number from URL."""
    url = "https://github.com/org/repo/pull/123"
    number = github_client._extract_pr_number(url)

    assert number == 123
