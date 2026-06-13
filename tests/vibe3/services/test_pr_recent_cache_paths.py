"""Regression tests for recent PR cache path resolution."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.clients.recent_pr_cache import RecentPRCache
from vibe3.services.pr.service import PRService


def test_refresh_recent_pr_cache_accepts_pathlike_git_common_dir() -> None:
    """Path-like git common dirs should resolve to the repo cache root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        store = SQLiteClient(db_path=str(repo_path / "test.db"))
        store.update_flow_state("feature-pathlike", flow_slug="pathlike")

        cache = RecentPRCache(repo_path)
        cache._save_cache(
            {
                "last_sync": (
                    datetime.now(timezone.utc) - timedelta(minutes=1)
                ).isoformat(),
                "prs": {
                    "feature-pathlike": {
                        "number": 404,
                        "title": "Pathlike PR",
                        "state": "OPEN",
                        "draft": False,
                        "url": "https://github.com/test/pr/404",
                        "head_branch": "feature-pathlike",
                        "base_branch": "main",
                        "merged_at": None,
                    }
                },
            }
        )

        github_client = MagicMock()
        git_client = MagicMock()
        git_client.get_git_common_dir.return_value = git_dir
        service = PRService(
            github_client=github_client,
            git_client=git_client,
            store=store,
        )

        branch_to_pr = service.refresh_recent_pr_cache()

        github_client.list_all_prs.assert_not_called()
        assert branch_to_pr["feature-pathlike"].number == 404
