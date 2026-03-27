"""Tests for PR upstream conflict detection."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import GitError, UserError
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_service import PRService


@pytest.fixture
def pr_service() -> PRService:
    """Create PR service fixture."""
    return PRService()


@pytest.fixture
def mock_github_client() -> MagicMock:
    """Mock GitHub client."""
    with patch("vibe3.services.pr_service.GitHubClient") as mock:
        yield mock


def test_create_draft_pr_blocks_on_conflict(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Merge conflict with origin/main blocks pr create."""
    mock_github_client.check_auth.return_value = True
    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = True

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", git):
            with pytest.raises(UserError, match="Merge conflict detected"):
                pr_service.create_draft_pr(title="T", body="B")


def test_mark_ready_blocks_on_conflict(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Merge conflict with origin/main blocks pr ready."""
    mock_github_client.check_auth.return_value = True
    mock_github_client.get_pr.return_value = PRResponse(
        number=1,
        title="",
        body="",
        state=PRState.OPEN,
        head_branch="f",
        base_branch="main",
        url="",
        draft=True,
    )
    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = True

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", git):
            with pytest.raises(UserError, match="Merge conflict detected"):
                pr_service.mark_ready(1)


def test_fetch_failure_does_not_block(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Network error during fetch only warns, does not block."""
    mock_github_client.check_auth.return_value = True
    mock_github_client.list_prs_for_branch.return_value = []
    mock_github_client.create_pr.return_value = PRResponse(
        number=1,
        title="",
        body="",
        state=PRState.OPEN,
        head_branch="f",
        base_branch="main",
        url="",
        draft=True,
    )
    git = MagicMock()
    git.fetch.side_effect = GitError("fetch", "network")
    git.check_merge_conflicts.return_value = False

    mock_store = MagicMock()
    mock_store.get_flow_state.return_value = {"branch": "f"}

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", git):
            with patch.object(pr_service, "store", mock_store):
                git.get_current_branch.return_value = "f"
                # Should NOT raise despite fetch failure
                pr = pr_service.create_draft_pr(title="T", body="B")
                assert pr.number == 1
