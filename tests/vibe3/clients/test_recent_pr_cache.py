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
            ci_status=None,
            created_at=None,
            updated_at=None,
            merged_at=None,
            closed_at=None,
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
            ci_status=None,
            created_at=None,
            updated_at=None,
            merged_at=datetime.now(timezone.utc),
            closed_at=None,
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


def test_upsert_branch_pr_inserts_new(cache: RecentPRCache) -> None:
    """New branch entry is persisted and retrievable via get_all_branch_prs()."""
    pr_data = {
        "number": 301,
        "title": "New PR",
        "state": "OPEN",
        "head_branch": "feature/new",
        "base_branch": "main",
        "url": "https://github.com/test/pr/301",
        "draft": False,
    }

    cache.upsert_branch_pr("feature/new", pr_data)

    cached = cache.get_all_branch_prs()
    assert "feature/new" in cached
    assert cached["feature/new"]["number"] == 301
    assert cached["feature/new"]["state"] == "OPEN"

    # Verify persistence by re-creating cache instance
    new_cache = RecentPRCache(cache.repo_path)
    cached_persisted = new_cache.get_all_branch_prs()
    assert cached_persisted["feature/new"]["number"] == 301


def test_upsert_branch_pr_overwrites_existing(cache: RecentPRCache) -> None:
    """Same branch key overwrites previous data."""
    initial_pr = {
        "number": 401,
        "title": "Initial PR",
        "state": "OPEN",
        "head_branch": "feature/update",
    }
    cache.upsert_branch_pr("feature/update", initial_pr)

    updated_pr = {
        "number": 402,
        "title": "Updated PR",
        "state": "CLOSED",
        "head_branch": "feature/update",
    }
    cache.upsert_branch_pr("feature/update", updated_pr)

    cached = cache.get_all_branch_prs()
    assert len(cached) == 1
    assert cached["feature/update"]["number"] == 402
    assert cached["feature/update"]["title"] == "Updated PR"
    assert cached["feature/update"]["state"] == "CLOSED"


def test_upsert_branch_pr_does_not_affect_other_branches(
    cache: RecentPRCache,
) -> None:
    """Upsert for branch A does not modify branch B's entry."""
    pr_a = {
        "number": 501,
        "title": "PR for branch A",
        "state": "OPEN",
        "head_branch": "feature/a",
    }
    pr_b = {
        "number": 502,
        "title": "PR for branch B",
        "state": "CLOSED",
        "head_branch": "feature/b",
    }

    cache.upsert_branch_pr("feature/a", pr_a)
    cache.upsert_branch_pr("feature/b", pr_b)

    cached = cache.get_all_branch_prs()
    assert len(cached) == 2
    assert cached["feature/a"]["number"] == 501
    assert cached["feature/b"]["number"] == 502

    # Update branch A, verify branch B unchanged
    pr_a_updated = {
        "number": 503,
        "title": "Updated PR for branch A",
        "state": "MERGED",
        "head_branch": "feature/a",
    }
    cache.upsert_branch_pr("feature/a", pr_a_updated)

    cached = cache.get_all_branch_prs()
    assert cached["feature/a"]["number"] == 503
    assert cached["feature/a"]["state"] == "MERGED"
    assert cached["feature/b"]["number"] == 502  # B unchanged
    assert cached["feature/b"]["state"] == "CLOSED"
