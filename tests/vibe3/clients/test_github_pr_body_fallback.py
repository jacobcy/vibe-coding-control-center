"""Tests for PR body fallback behavior in GitHub client."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_client import GitHubClient
from vibe3.models.pr import CreatePRRequest, PRResponse, PRState, UpdatePRRequest


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess.run for gh command execution."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock:
        yield mock


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
