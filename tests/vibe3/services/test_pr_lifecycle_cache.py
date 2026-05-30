"""Tests for PR title caching during PR lifecycle."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import RecentPRCache, SQLiteClient
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_service import PRService


def test_create_pr_updates_cache_title() -> None:
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
            result = service.create_pr(
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
            service.create_pr(
                title="Fix recursion",
                body="Body",
                base_branch="main",
            )

            # Verify handoff was appended (check event log)
            events = store.get_events("feature-branch")
            pr_events = [e for e in events if "pr" in e["event_type"].lower()]
            assert len(pr_events) > 0, "PR event should be recorded"


def test_refresh_open_pr_cache_updates_branch_cache_entries() -> None:
    """Batch open PR refresh should update flow_context_cache for each branch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        db_path = repo_path / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        store.update_flow_state("feature-one", flow_slug="one")
        store.update_flow_state("feature-two", flow_slug="two")

        open_prs = [
            PRResponse(
                number=101,
                title="Feature one PR",
                body="Body",
                state=PRState.OPEN,
                head_branch="feature-one",
                base_branch="main",
                url="https://github.com/test/pr/101",
                draft=False,
                is_ready=True,
                ci_passed=False,
                created_at=None,
                updated_at=None,
                merged_at=None,
                metadata=None,
            ),
            PRResponse(
                number=102,
                title="Feature two draft",
                body="Body",
                state=PRState.OPEN,
                head_branch="feature-two",
                base_branch="main",
                url="https://github.com/test/pr/102",
                draft=True,
                is_ready=False,
                ci_passed=False,
                created_at=None,
                updated_at=None,
                merged_at=None,
                metadata=None,
            ),
        ]

        github_client = MagicMock()
        github_client.list_all_prs.return_value = open_prs
        git_client = MagicMock()
        git_client.get_git_common_dir.return_value = str(git_dir)

        service = PRService(
            github_client=github_client,
            git_client=git_client,
            store=store,
        )
        branch_to_pr = service.refresh_open_pr_cache()

        assert set(branch_to_pr) == {"feature-one", "feature-two"}
        assert branch_to_pr["feature-one"].number == 101
        assert branch_to_pr["feature-two"].number == 102

        cache_one = store.get_flow_context_cache("feature-one")
        cache_two = store.get_flow_context_cache("feature-two")
        assert cache_one is not None
        assert cache_two is not None
        assert cache_one["pr_number"] == 101
        assert cache_one["pr_title"] == "Feature one PR"
        assert cache_two["pr_number"] == 102
        assert cache_two["pr_title"] == "Feature two draft"


def test_refresh_recent_pr_cache_skips_github_when_cache_is_fresh() -> None:
    """Recent PR cache should reuse fresh local snapshot for 10-minute window."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        db_path = repo_path / "test.db"
        store = SQLiteClient(db_path=str(db_path))
        store.update_flow_state("feature-cached", flow_slug="cached")

        cache = RecentPRCache(repo_path)
        cache._save_cache(
            {
                "last_sync": (
                    datetime.now(timezone.utc) - timedelta(minutes=5)
                ).isoformat(),
                "prs": {
                    "feature-cached": {
                        "number": 303,
                        "title": "Cached PR",
                        "state": "OPEN",
                        "draft": False,
                        "url": "https://github.com/test/pr/303",
                        "head_branch": "feature-cached",
                        "base_branch": "main",
                        "merged_at": None,
                    }
                },
            }
        )

        github_client = MagicMock()
        git_client = MagicMock()
        git_client.get_git_common_dir.return_value = str(git_dir)

        service = PRService(
            github_client=github_client,
            git_client=git_client,
            store=store,
        )
        branch_to_pr = service.refresh_recent_pr_cache()

        github_client.list_all_prs.assert_not_called()
        assert branch_to_pr["feature-cached"].number == 303
        context = store.get_flow_context_cache("feature-cached")
        assert context is not None
        assert context["pr_number"] == 303
        assert context["pr_title"] == "Cached PR"


def test_refresh_recent_pr_cache_can_skip_context_cache_sync() -> None:
    """PRService.refresh_recent_pr_cache(sync_context_cache=False)
    should not write to flow_context_cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        db_path = repo_path / "test.db"
        store = SQLiteClient(db_path=str(db_path))
        store.update_flow_state("feature-readonly", flow_slug="readonly")

        cache = RecentPRCache(repo_path)
        cache._save_cache(
            {
                "last_sync": (
                    datetime.now(timezone.utc) - timedelta(minutes=2)
                ).isoformat(),
                "prs": {
                    "feature-readonly": {
                        "number": 999,
                        "title": "Readonly PR",
                        "state": "OPEN",
                        "draft": False,
                        "url": "https://github.com/test/pr/999",
                        "head_branch": "feature-readonly",
                        "base_branch": "main",
                        "merged_at": None,
                    }
                },
            }
        )

        github_client = MagicMock()
        git_client = MagicMock()
        git_client.get_git_common_dir.return_value = str(git_dir)

        service = PRService(
            github_client=github_client,
            git_client=git_client,
            store=store,
        )

        with patch.object(service, "_sync_branch_context_cache") as mock_sync:
            branch_to_pr = service.refresh_recent_pr_cache(sync_context_cache=False)

            mock_sync.assert_not_called()

        assert branch_to_pr["feature-readonly"].number == 999
        context = store.get_flow_context_cache("feature-readonly")
        assert context is None
