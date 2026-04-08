"""Tests for issue title caching during flow initialization."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.services.flow_service import FlowService


def test_issue_flow_init_caches_issue_title_without_mutating_spec_ref() -> None:
    """Issue flow init should cache issue title but not write to spec_ref."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        git_client = GitClient()
        git_client.get_current_branch = lambda: "dev/issue-328"  # type: ignore

        # Mock GitHub API to return issue title
        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.view_issue.return_value = {
                "number": 328,
                "title": "Gemini quota failure should stop task",
                "body": "Description",
            }
            mock_gh_class.return_value = mock_gh

            service = FlowService(store=store, git_client=git_client)
            service.ensure_flow_for_branch("dev/issue-328")

            # Verify flow state does NOT have spec_ref set
            flow = store.get_flow_state("dev/issue-328")
            assert flow is not None
            assert flow["spec_ref"] is None, "spec_ref should not be set for issue flows"

            # Verify cache has issue number and title
            cache = store.get_flow_context_cache("dev/issue-328")
            assert cache is not None, "Cache should be initialized"
            assert cache["task_issue_number"] == 328
            assert (
                cache["issue_title"] == "Gemini quota failure should stop task"
            ), "Issue title should be cached"


def test_issue_flow_init_handles_github_failure_gracefully() -> None:
    """Issue flow init should succeed even if GitHub API fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        git_client = GitClient()
        git_client.get_current_branch = lambda: "task/issue-999"  # type: ignore

        # Mock GitHub API to fail
        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.view_issue.side_effect = Exception("GitHub API error")
            mock_gh_class.return_value = mock_gh

            service = FlowService(store=store, git_client=git_client)

            # Should NOT raise exception
            service.ensure_flow_for_branch("task/issue-999")

            # Verify cache has issue number but no title
            cache = store.get_flow_context_cache("task/issue-999")
            assert cache is not None, "Cache should be initialized even on GitHub failure"
            assert cache["task_issue_number"] == 999
            assert cache["issue_title"] is None, "Title should be None when GitHub fails"


def test_issue_flow_init_uses_existing_task_link() -> None:
    """Issue flow init should prefer existing task link over branch name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        git_client = GitClient()
        git_client.get_current_branch = lambda: "task/issue-436"  # type: ignore

        # Pre-create flow with different task issue
        store.update_flow_state("task/issue-436", flow_slug="test")
        store.add_issue_link("task/issue-436", 123, "task")

        # Mock GitHub API
        with patch("vibe3.clients.github_client.GitHubClient") as mock_gh_class:
            mock_gh = MagicMock()
            mock_gh.view_issue.return_value = {
                "number": 123,
                "title": "Linked issue title",
            }
            mock_gh_class.return_value = mock_gh

            service = FlowService(store=store, git_client=git_client)
            service._initialize_issue_flow_context("task/issue-436")

            # Verify cache uses linked issue (123), not branch issue (436)
            cache = store.get_flow_context_cache("task/issue-436")
            assert cache is not None
            assert cache["task_issue_number"] == 123, "Should use linked issue"
            assert cache["issue_title"] == "Linked issue title"