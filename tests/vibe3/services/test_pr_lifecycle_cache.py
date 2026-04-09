"""Tests for PR title caching during PR lifecycle."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_service import PRService


def test_create_draft_pr_updates_cache_title() -> None:
    """PR creation should cache PR number and title."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow first
        store.update_flow_state("feature-branch", flow_slug="test")

        mock_pr = PRResponse(
            number=512,
            title="Fix orchestra async startup recursion",
            body="Body",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            draft=True,
            url="https://github.com/test/pr/512",
            is_ready=False,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=None,
            metadata=None,
        )

        with (
            patch("vibe3.services.pr_service.GitHubClient") as mock_gh_class,
            patch("vibe3.services.pr_service.GitClient") as mock_git_class,
            patch("vibe3.services.pr_service.check_upstream_conflicts"),
        ):
            mock_gh = MagicMock()
            mock_gh.check_auth.return_value = True
            mock_gh.list_prs_for_branch.return_value = []
            mock_gh.create_pr.return_value = mock_pr
            mock_gh_class.return_value = mock_gh

            mock_git = MagicMock()
            mock_git.get_current_branch.return_value = "feature-branch"
            mock_git.push_branch.return_value = None
            mock_git_class.return_value = mock_git

            service = PRService(store=store)
            result = service.create_draft_pr(
                title="Fix orchestra async startup recursion",
                body="Body",
                base_branch="main",
            )

            assert result.number == 512

            # Verify cache was updated
            cache = store.get_flow_context_cache("feature-branch")
            assert cache is not None, "Cache should be updated after PR creation"
            assert cache["pr_number"] == 512
            assert (
                cache["pr_title"] == "Fix orchestra async startup recursion"
            ), "PR title should be cached"


def test_mark_ready_updates_cache_title() -> None:
    """Marking PR ready should update cache with latest PR title."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow with existing cache
        store.update_flow_state("feature-branch", flow_slug="test")
        store.upsert_flow_context_cache(
            branch="feature-branch",
            task_issue_number=None,
            issue_title=None,
            pr_number=512,
            pr_title="Old PR title",  # Old title
        )

        mock_pr = PRResponse(
            number=512,
            title="Updated PR title",  # New title after ready
            body="Body",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            draft=False,
            url="https://github.com/test/pr/512",
            is_ready=True,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=None,
            metadata=None,
        )

        with (
            patch("vibe3.services.pr_service.GitHubClient") as mock_gh_class,
            patch("vibe3.services.pr_service.GitClient") as mock_git_class,
            patch("vibe3.services.pr_service.check_upstream_conflicts"),
            patch(
                "vibe3.services.pr_service.SignatureService.resolve_for_branch",
                return_value="test-actor",
            ),
        ):
            mock_gh = MagicMock()
            mock_gh.check_auth.return_value = True
            mock_gh.get_pr.return_value = mock_pr
            mock_gh.mark_pr_ready.return_value = mock_pr
            mock_gh_class.return_value = mock_gh

            mock_git = MagicMock()
            mock_git.get_current_branch.return_value = "feature-branch"
            mock_git_class.return_value = mock_git

            service = PRService(store=store)
            result = service.mark_ready(512)

            assert result.number == 512
            assert result.draft is False

            # Verify cache was updated with new title
            cache = store.get_flow_context_cache("feature-branch")
            assert cache is not None
            assert (
                cache["pr_title"] == "Updated PR title"
            ), "Cache should reflect updated PR title"


def test_pr_create_appends_handoff_update() -> None:
    """PR creation should append update to handoff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow first
        store.update_flow_state("feature-branch", flow_slug="test")

        mock_pr = PRResponse(
            number=512,
            title="Fix recursion",
            body="Body",
            state=PRState.OPEN,
            head_branch="feature-branch",
            base_branch="main",
            draft=True,
            url="https://github.com/test/pr/512",
            is_ready=False,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=None,
            metadata=None,
        )

        with (
            patch("vibe3.services.pr_service.GitHubClient") as mock_gh_class,
            patch("vibe3.services.pr_service.GitClient") as mock_git_class,
            patch("vibe3.services.pr_service.check_upstream_conflicts"),
        ):
            mock_gh = MagicMock()
            mock_gh.check_auth.return_value = True
            mock_gh.list_prs_for_branch.return_value = []
            mock_gh.create_pr.return_value = mock_pr
            mock_gh_class.return_value = mock_gh

            mock_git = MagicMock()
            mock_git.get_current_branch.return_value = "feature-branch"
            mock_git.push_branch.return_value = None
            mock_git_class.return_value = mock_git

            service = PRService(store=store)
            service.create_draft_pr(
                title="Fix recursion",
                body="Body",
                base_branch="main",
            )

            # Verify handoff was appended (check event log)
            events = store.get_events("feature-branch")
            pr_events = [e for e in events if "pr" in e["event_type"].lower()]
            assert len(pr_events) > 0, "PR event should be recorded"
