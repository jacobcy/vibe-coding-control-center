"""Tests for PR service."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.pr_service import PRService
from vibe3.models.pr import PRMetadata, PRResponse, PRState


@pytest.fixture
def pr_service() -> PRService:
    """Create PR service fixture."""
    return PRService()


@pytest.fixture
def mock_github_client() -> MagicMock:
    """Mock GitHub client."""
    with patch("vibe3.services.pr_service.GitHubClient") as mock:
        yield mock


@pytest.fixture
def mock_git_client() -> MagicMock:
    """Mock Git client."""
    with patch("vibe3.services.pr_service.GitClient") as mock:
        yield mock


@pytest.fixture
def mock_store() -> MagicMock:
    """Mock Vibe3Store."""
    with patch("vibe3.services.pr_service.Vibe3Store") as mock:
        yield mock


def test_create_draft_pr_success(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Test create draft PR success."""
    mock_github_client.check_auth.return_value = True
    mock_github_client.get_current_branch.return_value = "feature-branch"
    mock_github_client.create_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=True,
    )

    metadata = PRMetadata(task_issue=101, flow_slug="test-flow")

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client"):
            pr_service.git_client.get_current_branch.return_value = "feature-branch"

            pr = pr_service.create_draft_pr(
                title="Test PR",
                body="Test body",
                base_branch="main",
                metadata=metadata,
            )

            assert pr.number == 123
            assert pr.draft is True
            mock_github_client.create_pr.assert_called_once()


def test_create_draft_pr_auth_failure(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Test create draft PR auth failure."""
    mock_github_client.check_auth.return_value = False

    with patch.object(pr_service, "github_client", mock_github_client):
        with pytest.raises(RuntimeError, match="Not authenticated"):
            pr_service.create_draft_pr(title="Test", body="Body")


def test_get_pr_success(pr_service: PRService, mock_github_client: MagicMock) -> None:
    """Test get PR success."""
    mock_github_client.get_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )

    with patch.object(pr_service, "github_client", mock_github_client):
        pr = pr_service.get_pr(pr_number=123)

        assert pr is not None
        assert pr.number == 123
        mock_github_client.get_pr.assert_called_once_with(123, None)


def test_mark_ready_success(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Test mark PR as ready success."""
    mock_pr = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=True,
    )

    mock_github_client.check_auth.return_value = True
    mock_github_client.get_pr.return_value = mock_pr
    mock_github_client.mark_ready.return_value = mock_pr

    with patch.object(pr_service, "github_client", mock_github_client):
        pr = pr_service.mark_ready(123)

        assert pr.number == 123
        mock_github_client.mark_ready.assert_called_once_with(123)


def test_merge_pr_success(pr_service: PRService, mock_github_client: MagicMock) -> None:
    """Test merge PR success."""
    mock_pr = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.MERGED,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )

    mock_github_client.check_auth.return_value = True
    mock_github_client.get_pr.return_value = mock_pr
    mock_github_client.merge_pr.return_value = mock_pr

    with patch.object(pr_service, "github_client", mock_github_client):
        pr = pr_service.merge_pr(123)

        assert pr.state == PRState.MERGED
        mock_github_client.merge_pr.assert_called_once_with(123)
