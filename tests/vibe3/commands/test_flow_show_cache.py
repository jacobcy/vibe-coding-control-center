"""Tests for flow projection using cache."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.services.flow_projection_service import FlowProjectionService


def test_flow_projection_uses_cached_issue_title() -> None:
    """FlowProjectionService should use cached issue title."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow with cached issue title
        store.update_flow_state("task/issue-436", flow_slug="test_436")
        store.add_issue_link("task/issue-436", 436, "task")
        store.upsert_flow_context_cache(
            branch="task/issue-436",
            task_issue_number=436,
            issue_title="Use local cache before remote hydrate",
            pr_number=None,
            pr_title=None,
        )

        # Mock GitHub client
        with patch("vibe3.services.flow_projection_service.GitHubClient") as mock_gh:
            mock_gh_instance = MagicMock()
            mock_gh_instance.view_issue.return_value = None  # Should not be called
            mock_gh.return_value = mock_gh_instance

            # Create service with store (inside patch context)
            projection_service = FlowProjectionService(store=store)

            titles, net_err = projection_service.get_issue_titles([436])

            # Should have returned cached title without GitHub call
            assert titles.get(436) == "Use local cache before remote hydrate"
            assert net_err is False  # No network error when using cache
            # GitHub API should not have been called
            mock_gh_instance.view_issue.assert_not_called()


def test_flow_projection_falls_back_to_github_on_cache_miss() -> None:
    """FlowProjectionService should fetch from GitHub when cache missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow without cache
        store.update_flow_state("task/issue-999", flow_slug="test_999")
        store.add_issue_link("task/issue-999", 999, "task")

        # Mock GitHub client
        with patch("vibe3.services.flow_projection_service.GitHubClient") as mock_gh:
            mock_gh_instance = MagicMock()
            mock_gh_instance.view_issue.return_value = {
                "number": 999,
                "title": "Fetched from GitHub",
            }
            mock_gh.return_value = mock_gh_instance

            # Create service with store (inside patch context)
            projection_service = FlowProjectionService(store=store)

            titles, net_err = projection_service.get_issue_titles([999])

            # Should have fetched from GitHub
            assert titles.get(999) == "Fetched from GitHub"
            assert net_err is False  # GitHub call succeeded
            # GitHub API should have been called
            mock_gh_instance.view_issue.assert_called_once_with(999)


def test_flow_projection_returns_empty_on_github_failure() -> None:
    """FlowProjectionService should handle GitHub failures gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        store.update_flow_state("task/issue-404", flow_slug="test_404")
        store.add_issue_link("task/issue-404", 404, "task")

        # Mock GitHub client to fail
        with patch("vibe3.services.flow_projection_service.GitHubClient") as mock_gh:
            mock_gh_instance = MagicMock()
            mock_gh_instance.view_issue.side_effect = Exception("GitHub error")
            mock_gh.return_value = mock_gh_instance

            # Create service with store (inside patch context)
            projection_service = FlowProjectionService(store=store)

            titles, net_err = projection_service.get_issue_titles([404])

            # Should indicate network error
            assert net_err is True
            # Should not have title
            assert 404 not in titles
