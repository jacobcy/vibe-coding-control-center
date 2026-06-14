"""Unit tests for RecentPRCache."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vibe3.clients.recent_pr_cache import RecentPRCache
from vibe3.models.pr import PRResponse, PRState


class MockGitHubClient:
    """Mock GitHub client for testing recent PR cache."""

    def __init__(self, prs: list[PRResponse]) -> None:
        self.prs = prs

    def list_all_prs(
        self, state: str = "all", limit: int = 50, *, repo: str | None = None
    ) -> list[PRResponse]:
        assert state == "all"
        _ = repo
        return self.prs[:limit]


@pytest.fixture
def temp_repo_path(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "vibe3").mkdir()
    return repo


@pytest.fixture
def cache(temp_repo_path: Path) -> RecentPRCache:
    return RecentPRCache(temp_repo_path)


def test_recent_pr_cache_missing_file_returns_empty(cache: RecentPRCache) -> None:
    data = cache._load_cache()
    assert data["last_sync"] is None
    assert data["prs"] == {}


def test_recent_pr_cache_is_fresh_uses_last_sync_window(
    cache: RecentPRCache,
) -> None:
    fresh_sync = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    stale_sync = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    cache._save_cache({"last_sync": fresh_sync, "prs": {}})
    assert cache.is_fresh(max_age_minutes=10) is True

    cache._save_cache({"last_sync": stale_sync, "prs": {}})
    assert cache.is_fresh(max_age_minutes=10) is False


def test_recent_pr_cache_sync_replaces_snapshot(cache: RecentPRCache) -> None:
    prs = [
        PRResponse(
            number=201,
            title="Open PR",
            body="Body",
            state=PRState.OPEN,
            head_branch="feature/open",
            base_branch="main",
            url="https://github.com/test/pr/201",
            draft=False,
            is_ready=True,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=None,
            metadata=None,
        ),
        PRResponse(
            number=202,
            title="Merged PR",
            body="Body",
            state=PRState.CLOSED,
            head_branch="feature/merged",
            base_branch="main",
            url="https://github.com/test/pr/202",
            draft=False,
            is_ready=True,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=datetime.now(timezone.utc),
            metadata=None,
        ),
    ]

    count = cache.sync(MockGitHubClient(prs), limit=50)
    assert count == 2

    cached = cache.get_all_branch_prs()
    assert set(cached) == {"feature/open", "feature/merged"}
    assert cached["feature/open"]["number"] == 201
    assert cached["feature/open"]["state"] == "OPEN"
    assert cached["feature/merged"]["number"] == 202
    assert cached["feature/merged"]["state"] == "CLOSED"
    # Verify merged_at is a valid ISO 8601 string
    merged_at = cached["feature/merged"]["merged_at"]
    assert merged_at is not None
    datetime.fromisoformat(merged_at)
