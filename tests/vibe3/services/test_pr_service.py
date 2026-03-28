"""Tests for PR service."""

from unittest.mock import MagicMock, patch

import pytest

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


@pytest.fixture
def no_conflict_git() -> MagicMock:
    """Mock git client with no merge conflicts (fetch + dry-run clean)."""
    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = False
    return git


def test_create_draft_pr_success(
    pr_service: PRService, mock_github_client: MagicMock, no_conflict_git: MagicMock
) -> None:
    """Test create draft PR success."""
    mock_github_client.check_auth.return_value = True
    mock_github_client.get_current_branch.return_value = "feature-branch"
    mock_github_client.list_prs_for_branch.return_value = []
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

    mock_store = MagicMock()
    mock_store.get_flow_state.return_value = {
        "branch": "feature-branch",
        "flow_slug": "test-flow",
        "task_issue_number": 101,
        "spec_ref": None,
        "planner_actor": None,
        "executor_actor": None,
    }

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", no_conflict_git):
            with patch.object(pr_service, "store", mock_store):
                no_conflict_git.get_current_branch.return_value = "feature-branch"

                pr = pr_service.create_draft_pr(
                    title="Test PR",
                    body="Test body",
                    base_branch="main",
                )

                assert pr.number == 123
                assert pr.draft is True
                mock_github_client.create_pr.assert_called_once()
                no_conflict_git.fetch.assert_called_once_with("origin", "main")
                no_conflict_git.push_branch.assert_called_once_with(
                    "feature-branch", set_upstream=True
                )
                assert mock_store.get_flow_state.call_count == 2
                mock_store.update_flow_state.assert_called_once_with(
                    "feature-branch",
                    pr_number=123,
                    pr_ready_for_review=False,
                    latest_actor="workflow",
                )
                mock_store.add_event.assert_called_once_with(
                    "feature-branch",
                    "pr_draft",
                    "workflow",
                    "Draft PR #123 created: https://github.com/org/repo/pull/123",
                )


def test_create_draft_pr_auth_failure(
    pr_service: PRService, mock_github_client: MagicMock
) -> None:
    """Test create draft PR auth failure."""
    mock_github_client.check_auth.return_value = False

    with patch.object(pr_service, "github_client", mock_github_client):
        with pytest.raises(RuntimeError, match="Not authenticated"):
            pr_service.create_draft_pr(title="Test", body="Body")


def test_create_draft_pr_duplicate_branch_pr(
    pr_service: PRService, mock_github_client: MagicMock, no_conflict_git: MagicMock
) -> None:
    mock_github_client.check_auth.return_value = True
    mock_github_client.list_prs_for_branch.return_value = [
        PRResponse(
            number=321,
            title="Existing PR",
            body="",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            url="https://github.com/org/repo/pull/321",
            draft=True,
        )
    ]

    hydrated_pr = PRResponse(
        number=321,
        title="Existing PR",
        body="Existing body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/321",
        draft=True,
    )
    mock_github_client.get_pr.return_value = hydrated_pr

    mock_store = MagicMock()
    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", no_conflict_git):
            with patch.object(pr_service, "store", mock_store):
                no_conflict_git.get_current_branch.return_value = "feature-branch"

                pr = pr_service.create_draft_pr(title="Test", body="Body")

                assert pr.number == 321
                assert pr.body == "Existing body"
                no_conflict_git.push_branch.assert_not_called()
                mock_github_client.get_pr.assert_called_once_with(321)
                mock_store.update_flow_state.assert_called_once_with(
                    "feature-branch",
                    pr_number=321,
                    pr_ready_for_review=False,
                    latest_actor="workflow",
                )


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
    pr_service: PRService, mock_github_client: MagicMock, no_conflict_git: MagicMock
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
    mock_github_client.mark_ready.return_value = mock_pr.model_copy(
        update={"draft": False}
    )
    mock_store = MagicMock()

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", no_conflict_git):
            with patch.object(pr_service, "store", mock_store):
                pr = pr_service.mark_ready(123)

                assert pr.number == 123
                mock_github_client.mark_ready.assert_called_once_with(123)
                no_conflict_git.fetch.assert_called_once_with("origin", "main")
                mock_store.update_flow_state.assert_called_once_with(
                    "feature-branch",
                    pr_number=123,
                    pr_ready_for_review=True,
                    latest_actor="workflow",
                )
                mock_store.add_event.assert_called_once_with(
                    "feature-branch",
                    "pr_ready",
                    "workflow",
                    "PR #123 marked as ready for review",
                )


def test_mark_ready_already_ready_syncs_state(
    pr_service: PRService, mock_github_client: MagicMock, no_conflict_git: MagicMock
) -> None:
    """mark_ready should confirm and sync when PR is already ready."""
    ready_pr = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )

    mock_github_client.check_auth.return_value = True
    mock_github_client.get_pr.return_value = ready_pr
    mock_store = MagicMock()

    with patch.object(pr_service, "github_client", mock_github_client):
        with patch.object(pr_service, "git_client", no_conflict_git):
            with patch.object(pr_service, "store", mock_store):
                pr = pr_service.mark_ready(123)

    assert pr.number == 123
    mock_github_client.mark_ready.assert_not_called()
    mock_store.update_flow_state.assert_called_once_with(
        "feature-branch",
        pr_number=123,
        pr_ready_for_review=True,
        latest_actor="workflow",
    )
    mock_store.add_event.assert_not_called()
