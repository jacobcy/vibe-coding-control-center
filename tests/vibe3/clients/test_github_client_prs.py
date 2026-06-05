"""Tests for GitHub client."""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_review_ops import ReviewMixin
from vibe3.exceptions import GitHubError, UserError
from vibe3.models.pr import CreatePRRequest, PRResponse, PRState, UpdatePRRequest


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess.run."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock:
        yield mock


def test_check_auth_success_with_token(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check success with GH_TOKEN."""
    with patch.dict(os.environ, {"GH_TOKEN": "test-token"}):
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "testuser\n"

        result = github_client.check_auth()

        assert result is True
        mock_subprocess.assert_called_once_with(
            ["gh", "api", "user", "-q", ".login"],
            capture_output=True,
            text=True,
            timeout=5,
        )


def test_check_auth_success_without_token(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check success without GH_TOKEN (fallback to gh auth status)."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove GH_TOKEN if present
        os.environ.pop("GH_TOKEN", None)

        mock_subprocess.return_value.returncode = 0

        result = github_client.check_auth()

        assert result is True
        mock_subprocess.assert_called_once_with(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )


def test_check_auth_failure_with_token(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check failure with GH_TOKEN."""
    with patch.dict(os.environ, {"GH_TOKEN": "invalid-token"}):
        mock_subprocess.return_value.returncode = 1

        result = github_client.check_auth()

        assert result is False


def test_check_auth_failure_without_token(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """Test auth check failure without GH_TOKEN."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove GH_TOKEN if present
        os.environ.pop("GH_TOKEN", None)

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

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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


def test_get_pr_enriches_failed_checks_with_category_and_command() -> None:
    """Test get_pr enriches failed CI checks with failure metadata."""
    client = GitHubClient()

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
    checks_data = [
        {
            "name": "Lint & Test",
            "state": "FAILURE",
            "bucket": "fail",
            "link": "https://github.com/org/repo/actions/runs/26262915490/job/77300075332",
        }
    ]
    run_data = {
        "jobs": [
            {
                "name": "Lint & Test",
                "conclusion": "failure",
                "steps": [
                    {"name": "Setup", "conclusion": "success"},
                    {"name": "Run Python tests (pytest)", "conclusion": "failure"},
                ],
            }
        ]
    }

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps(pr_data), stderr=""),
            MagicMock(returncode=0, stdout=json.dumps(checks_data), stderr=""),
            MagicMock(returncode=0, stdout=json.dumps(run_data), stderr=""),
        ]

        pr = client.get_pr(pr_number=123)

    assert pr is not None
    assert getattr(pr.ci_checks[0], "failure_category", None) == "pytest"
    assert getattr(pr.ci_checks[0], "failure_command", None) == (
        "gh run view 26262915490 --job 77300075332 --log-failed"
    )


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
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "ready", "123"],
            stderr="pull request is already ready for review",
        )

        with pytest.raises(UserError) as exc_info:
            github_client.mark_ready(123)

    assert "PR ready failed" in str(exc_info.value)


def test_merge_pr_maps_non_recoverable_error_to_github_error(
    github_client: GitHubClient,
) -> None:
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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


def test_create_pr_repairs_empty_body_after_creation(
    github_client: GitHubClient, mock_subprocess: MagicMock
) -> None:
    """create_pr should patch body when remote response unexpectedly has empty body."""
    mock_subprocess.return_value.stdout = "https://github.com/org/repo/pull/123\n"
    mock_subprocess.return_value.returncode = 0

    empty_body_pr = PRResponse(
        number=123,
        title="Test PR",
        body="",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=True,
    )
    fixed_pr = empty_body_pr.model_copy(update={"body": "Generated body"})

    with (
        patch.object(github_client, "get_pr", return_value=empty_body_pr),
        patch.object(github_client, "update_pr", return_value=fixed_pr) as mock_update,
    ):
        request = CreatePRRequest(
            title="Test PR",
            body="Generated body",
            head_branch="feature-branch",
            base_branch="main",
            draft=True,
        )

        pr = github_client.create_pr(request)

    assert pr.body == "Generated body"
    mock_update.assert_called_once_with(
        UpdatePRRequest(
            number=123,
            title=None,
            body="Generated body",
            draft=None,
            base_branch=None,
        )
    )


@pytest.fixture
def review_mixin():
    """Create ReviewMixin instance."""
    return ReviewMixin()


def test_get_pr_diff_file_limit_error(review_mixin):
    """Test that PR diff with >300 files raises UserError."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "file1.py\nfile2.py\nfile3.py\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = review_mixin.get_pr_files(42)

        assert result == ["file1.py", "file2.py", "file3.py"]


def test_get_pr_files_other_error(review_mixin):
    """Test that other PR files errors raise GitHubError."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
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
