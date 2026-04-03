"""Tests for PR upstream conflict detection."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import GitError, UserError
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_service import PRService


@pytest.fixture
def pr_service() -> PRService:
    """Create PR service fixture."""
    github_client = MagicMock()
    git_client = MagicMock()
    store = MagicMock()
    version_service = MagicMock()
    service = PRService(
        github_client=github_client,
        git_client=git_client,
        store=store,
        version_service=version_service,
    )
    service.briefing_service = MagicMock()
    return service


@pytest.fixture
def mock_github_client() -> MagicMock:
    """Mock GitHub client."""
    return MagicMock()


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


def test_create_conflict_check_uses_base_branch(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Conflict check should align with chosen base branch."""
    mock_github_client.check_auth.return_value = True
    mock_github_client.list_prs_for_branch.return_value = []
    mock_github_client.create_pr.return_value = PRResponse(
        number=7,
        title="",
        body="",
        state=PRState.OPEN,
        head_branch="feature",
        base_branch="develop",
        url="",
        draft=True,
    )

    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = False
    git.get_current_branch.return_value = "feature"
    git.push_branch.return_value = None

    mock_store = MagicMock()
    mock_store.get_flow_state.return_value = {}

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", git):
            with patch.object(pr_service, "store", mock_store):
                pr_service.create_draft_pr(
                    title="T",
                    body="B",
                    base_branch="develop",
                )

    git.fetch.assert_called_once_with("origin", "develop")
    git.check_merge_conflicts.assert_called_once_with("origin/develop")
    mock_github_client.create_pr.assert_called_once()


def test_mark_ready_conflict_check_uses_pr_base(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """mark_ready should use PR base branch when checking conflicts."""
    mock_pr = PRResponse(
        number=2,
        title="",
        body="",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="release",
        url="",
        draft=True,
    )

    mock_github_client.check_auth.return_value = True
    mock_github_client.get_pr.return_value = mock_pr
    mock_github_client.mark_ready.return_value = mock_pr

    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = False

    mock_store = MagicMock()

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", git):
            with patch.object(pr_service, "store", mock_store):
                pr_service.mark_ready(2)

    git.fetch.assert_called_once_with("origin", "release")
    git.check_merge_conflicts.assert_called_once_with("origin/release")


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

    mock_store = MagicMock()

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "store", mock_store):
            # Mock SignatureService so result is deterministic regardless of git config
            with patch(
                "vibe3.services.pr_service.SignatureService.resolve_for_branch",
                return_value="test-actor",
            ):
                pr = pr_service.merge_pr(123)

            assert pr.state == PRState.MERGED
            mock_github_client.merge_pr.assert_called_once_with(123)
            mock_store.update_flow_state.assert_called_once_with(
                "feature-branch",
                flow_status="done",
                latest_actor="test-actor",
            )
            mock_store.add_event.assert_called_once_with(
                "feature-branch",
                "pr_merge",
                "test-actor",
                "PR #123 merged",
            )
