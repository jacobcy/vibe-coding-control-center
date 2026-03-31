"""Tests for GitHub client."""

import json
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


def _client() -> GitHubClient:
    return GitHubClient()


# -- list_issues_with_assignees --


def test_list_issues_with_assignees_success():
    client = _client()
    payload = [{"number": 1, "title": "T", "labels": [], "assignees": [], "url": "u"}]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        result = client.list_issues_with_assignees(limit=10)
    assert len(result) == 1
    assert result[0]["number"] == 1


def test_list_issues_with_assignees_failure_returns_empty():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="auth error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        result = client.list_issues_with_assignees()
    assert result == []


def test_list_issues_with_assignees_passes_repo():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="[]")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.list_issues_with_assignees(repo="owner/repo")
    cmd = mock_run.call_args[0][0]
    assert "--repo" in cmd
    assert "owner/repo" in cmd


# -- close_issue --


def test_close_issue_success():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.close_issue(42) is True


def test_close_issue_with_comment():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.close_issue(42, comment="closing because done")
    cmd = mock_run.call_args[0][0]
    assert "--comment" in cmd


def test_close_issue_failure_returns_false():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="not found", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.close_issue(999) is False


# -- add_comment --


def test_add_comment_success():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.add_comment(42, "hello") is True


def test_add_comment_failure_returns_false():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.add_comment(42, "hello") is False


def test_add_comment_passes_repo():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.add_comment(42, "hi", repo="owner/repo")
    cmd = mock_run.call_args[0][0]
    assert "--repo" in cmd


# -- get_pr_for_issue --


def test_get_pr_for_issue_found():
    client = _client()
    payload = [
        {
            "number": 10,
            "closingIssuesReferences": [{"number": 42}],
        }
    ]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr == 10


def test_get_pr_for_issue_not_found():
    client = _client()
    payload = [{"number": 10, "closingIssuesReferences": [{"number": 99}]}]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr is None


def test_get_pr_for_issue_gh_failure():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr is None
