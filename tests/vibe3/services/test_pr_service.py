"""Tests for PR service."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import GitError, UserError
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
            pr_service.briefing_service.publish_briefing.assert_called_once_with(
                123, requested_reviewers=None
            )
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


def test_pr_service_preserves_falsey_injected_dependencies() -> None:
    """Injected PR collaborators should be preserved even if they are falsey."""
    github_client = MagicMock()
    github_client.__bool__.return_value = False
    git_client = MagicMock()
    git_client.__bool__.return_value = False
    store = MagicMock()
    store.__bool__.return_value = False
    version_service = MagicMock()
    version_service.__bool__.return_value = False

    service = PRService(
        github_client=github_client,
        git_client=git_client,
        store=store,
        version_service=version_service,
    )

    assert service.github_client is github_client
    assert service.git_client is git_client
    assert service.store is store
    assert service.version_service is version_service
    assert service.briefing_service.github_client is github_client


def test_create_draft_pr_push_failure_surfaces_upstream_guidance(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    gh_instance = pr_service.github_client
    gh_instance.check_auth.return_value = True
    gh_instance.list_prs_for_branch.return_value = []

    no_conflict_git.get_current_branch.return_value = "task/issue-337"
    no_conflict_git.push_branch.side_effect = GitError(
        "push -u origin task/issue-337",
        "fatal: cannot push some refs",
    )

    with patch.object(pr_service, "git_client", no_conflict_git):
        with pytest.raises(UserError) as exc_info:
            pr_service.create_draft_pr(title="Test PR", body="Test body")

    message = str(exc_info.value)
    assert "git branch -vv" in message
    assert "tracking origin/main" in message
    assert "gh pr create" in message


def test_close_pr_calls_gh_pr_close(pr_service: PRService) -> None:
    """Test close_pr calls gh pr close with correct parameters."""
    gh_instance = pr_service.github_client
    gh_instance.close_pr.return_value = True

    result = pr_service.close_pr(123, comment="Closing PR")

    assert result is True
    gh_instance.close_pr.assert_called_once_with(123, comment="Closing PR")


def test_close_pr_returns_success_marker(pr_service: PRService) -> None:
    """Test close_pr returns success marker."""
    gh_instance = pr_service.github_client
    gh_instance.close_pr.return_value = True

    result = pr_service.close_pr(123)

    assert result is True


def test_pr_service_close_open_pr_for_flow(pr_service: PRService) -> None:
    """Test PRService can close open PR for a flow branch."""
    gh_instance = pr_service.github_client
    gh_instance.list_prs_for_branch.return_value = [
        PRResponse(
            number=123,
            title="Test PR",
            body="Test body",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            url="https://github.com/org/repo/pull/123",
            draft=False,
        )
    ]
    gh_instance.close_pr.return_value = True

    result = pr_service.close_open_pr_for_flow(
        branch="feature-branch", comment="Abandoning flow"
    )

    assert result == 123  # Returns PR number
    gh_instance.list_prs_for_branch.assert_called_once_with(
        "feature-branch", state="open"
    )
    gh_instance.close_pr.assert_called_once_with(123, comment="Abandoning flow")


def test_mark_ready_publishes_loc_comment(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    """Test that mark_ready publishes LOC comment."""
    from vibe3.services.pr_loc_comment_service import PRLocCommentService

    # Setup mocks
    gh_instance = pr_service.github_client
    gh_instance.check_auth.return_value = True
    gh_instance.get_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=True,  # Draft PR to trigger mark_ready
    )
    gh_instance.mark_ready.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,  # Now ready
    )

    # Add LOC comment service mock
    loc_service_mock = MagicMock(spec=PRLocCommentService)
    pr_service.loc_comment_service = loc_service_mock

    # Call mark_ready
    with patch.object(pr_service, "git_client", no_conflict_git):
        result = pr_service.mark_ready(123)

    # Verify LOC comment was published
    loc_service_mock.publish_loc_summary.assert_called_once_with(123)

    # Verify PR was marked ready
    gh_instance.mark_ready.assert_called_once_with(123)
    assert result.draft is False


def test_loc_comment_idempotent_update(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    """Test that LOC comment updates existing comment on re-run."""
    from vibe3.services.pr_loc_comment_service import PRLocCommentService

    # Setup mocks for already-ready PR (is_already_ready=True)
    gh_instance = pr_service.github_client
    gh_instance.check_auth.return_value = True
    gh_instance.get_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,  # Already ready
    )

    # Add LOC comment service mock
    loc_service_mock = MagicMock(spec=PRLocCommentService)
    pr_service.loc_comment_service = loc_service_mock

    # Call mark_ready on already-ready PR
    with patch.object(pr_service, "git_client", no_conflict_git):
        result = pr_service.mark_ready(123)

    # Verify LOC comment was still published (idempotent update)
    loc_service_mock.publish_loc_summary.assert_called_once_with(123)

    # Verify PR remains ready
    assert result.draft is False


def test_mark_ready_handles_loc_comment_failure(
    pr_service: PRService, no_conflict_git: MagicMock
) -> None:
    """Test that LOC comment failure doesn't block mark_ready."""
    from vibe3.services.pr_loc_comment_service import PRLocCommentService

    # Setup mocks
    gh_instance = pr_service.github_client
    gh_instance.check_auth.return_value = True
    gh_instance.get_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=True,
    )
    gh_instance.mark_ready.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )

    # Add LOC comment service mock that raises exception
    loc_service_mock = MagicMock(spec=PRLocCommentService)
    loc_service_mock.publish_loc_summary.side_effect = Exception("LOC error")
    pr_service.loc_comment_service = loc_service_mock

    # Call mark_ready - should not fail
    with patch.object(pr_service, "git_client", no_conflict_git):
        result = pr_service.mark_ready(123)

    # Verify LOC comment was attempted
    loc_service_mock.publish_loc_summary.assert_called_once_with(123)

    # Verify PR was still marked ready despite LOC error
    gh_instance.mark_ready.assert_called_once_with(123)
    assert result.draft is False
