"""Tests for PR service."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_service import PRService


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    with patch("vibe3.services.pr_service.GitHubClient") as mock:
        yield mock


@pytest.fixture
def pr_service(mock_github_client):
    """Create PR service fixture with mocked briefing service."""
    gh_instance = mock_github_client.return_value
    service = PRService(github_client=gh_instance)
    service.briefing_service = MagicMock()
    return service


@pytest.fixture
def no_conflict_git():
    """Mock git client with no merge conflicts."""
    git = MagicMock()
    git.fetch.return_value = None
    git.check_merge_conflicts.return_value = False
    return git


def test_create_draft_pr_success(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    """Test create draft PR success."""
    gh_instance = pr_service.github_client
    gh_instance.check_auth.return_value = True
    gh_instance.get_current_branch.return_value = "feature-branch"
    gh_instance.list_prs_for_branch.return_value = []
    gh_instance.create_pr.return_value = PRResponse(
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
    mock_store.get_flow_state.return_value = {"branch": "feature-branch"}
    mock_store.get_issue_links.return_value = []

    with patch.object(pr_service, "git_client", no_conflict_git):
        with patch.object(pr_service, "store", mock_store):
            no_conflict_git.get_current_branch.return_value = "feature-branch"
            pr = pr_service.create_draft_pr(title="Test PR", body="Test body")

            assert pr.number == 123
            gh_instance.create_pr.assert_called_once()
            mock_store.update_flow_state.assert_called_once()
            mock_store.add_event.assert_called_once()


def test_mark_ready_success(pr_service: PRService, no_conflict_git: MagicMock) -> None:
    """Test mark PR as ready success."""
    gh_instance = pr_service.github_client
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

    gh_instance.check_auth.return_value = True
    gh_instance.get_pr.return_value = mock_pr
    gh_instance.mark_ready.return_value = mock_pr.model_copy(update={"draft": False})
    mock_store = MagicMock()
    mock_store.get_issue_links.return_value = []

    with patch.object(pr_service, "git_client", no_conflict_git):
        with patch.object(pr_service, "store", mock_store):
            pr = pr_service.mark_ready(123)

            assert pr.number == 123
            gh_instance.mark_ready.assert_called_once_with(123)
            pr_service.briefing_service.publish_briefing.assert_called_once_with(123)
            mock_store.add_event.assert_called_once()


def test_mark_ready_briefing_failure_still_records_event(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    """PR should be marked ready and local state updated even if briefing fails."""
    gh_instance = pr_service.github_client
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

    gh_instance.check_auth.return_value = True
    gh_instance.get_pr.return_value = mock_pr
    gh_instance.mark_ready.return_value = mock_pr.model_copy(update={"draft": False})

    # Simulate briefing failure
    pr_service.briefing_service.publish_briefing.side_effect = RuntimeError("API Fail")

    mock_store = MagicMock()
    mock_store.get_issue_links.return_value = []

    with patch.object(pr_service, "git_client", no_conflict_git):
        with patch.object(pr_service, "store", mock_store):
            # Should NOT raise
            pr = pr_service.mark_ready(123)

            assert pr.number == 123
            gh_instance.mark_ready.assert_called_once_with(123)
            # Both flow sync and event should happen
            mock_store.update_flow_state.assert_called()
            mock_store.add_event.assert_called_once()
