"""Unit tests for MergedPRCache."""

from pathlib import Path
from typing import Any

import pytest

from vibe3.clients.merged_pr_cache import MergedPRCache


class MockGitHubClient:
    """Mock GitHub client for testing."""

    def __init__(self, merged_prs: list[dict[str, Any]]) -> None:
        self.merged_prs = merged_prs

    def list_merged_prs(self, limit: int | None = 100) -> list[dict[str, Any]]:
        """Return mock merged PRs."""
        if limit is None:
            return self.merged_prs
        return self.merged_prs[:limit]


@pytest.fixture
def temp_repo_path(tmp_path: Path) -> Path:
    """Create temporary repo path with .git/vibe3 directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_dir = repo / ".git"
    git_dir.mkdir()
    vibe3_dir = git_dir / "vibe3"
    vibe3_dir.mkdir()
    return repo


@pytest.fixture
def cache(temp_repo_path: Path) -> MergedPRCache:
    """Create cache instance with temp repo path."""
    return MergedPRCache(temp_repo_path)


def test_load_empty_cache_on_missing_file(cache: MergedPRCache) -> None:
    """Missing cache file returns empty structure, no error."""
    data = cache._load_cache()
    assert data["last_sync"] is None
    assert data["prs"] == {}


def test_save_and_load_roundtrip(cache: MergedPRCache) -> None:
    """Write cache, read it back, data matches."""
    test_data = {
        "last_sync": "2024-01-15T10:00:00Z",
        "prs": {
            "123": {
                "number": 123,
                "headRefName": "feature/foo",
                "body": "Closes #456",
                "mergedAt": "2024-01-10T12:00:00Z",
                "issue": 456,
            }
        },
    }
    cache._save_cache(test_data)
    loaded = cache._load_cache()
    assert loaded == test_data


def test_load_cache_on_corrupted_json(cache: MergedPRCache) -> None:
    """Corrupted cache file returns empty structure."""
    cache_file = cache.cache_file
    cache_file.write_text("not valid json {")

    data = cache._load_cache()
    assert data["last_sync"] is None
    assert data["prs"] == {}


def test_get_merged_pr_for_issue_hit(cache: MergedPRCache) -> None:
    """Cached issue→PR mapping resolves correctly."""
    test_data = {
        "last_sync": "2024-01-15T10:00:00Z",
        "prs": {
            "100": {
                "number": 100,
                "headRefName": "feature/a",
                "body": "Closes #456",
                "mergedAt": "2024-01-10T12:00:00Z",
                "issue": 456,
            },
            "101": {
                "number": 101,
                "headRefName": "feature/b",
                "body": "Fixes #789",
                "mergedAt": "2024-01-11T12:00:00Z",
                "issue": 789,
            },
        },
    }
    cache._save_cache(test_data)

    result = cache.get_merged_pr_for_issue(456)
    assert result is not None
    assert result["number"] == 100
    assert result["issue"] == 456

    result = cache.get_merged_pr_for_issue(789)
    assert result is not None
    assert result["number"] == 101
    assert result["issue"] == 789


def test_get_merged_pr_for_issue_miss(cache: MergedPRCache) -> None:
    """Uncached issue returns None."""
    test_data = {
        "last_sync": "2024-01-15T10:00:00Z",
        "prs": {
            "100": {
                "number": 100,
                "headRefName": "feature/a",
                "body": "Closes #456",
                "mergedAt": "2024-01-10T12:00:00Z",
                "issue": 456,
            }
        },
    }
    cache._save_cache(test_data)

    result = cache.get_merged_pr_for_issue(999)
    assert result is None


def test_sync_merges_new_prs(cache: MergedPRCache) -> None:
    """sync() adds new PRs without losing existing ones."""
    # Pre-populate cache with one PR
    cache._save_cache(
        {
            "last_sync": "2024-01-10T10:00:00Z",
            "prs": {
                "100": {
                    "number": 100,
                    "headRefName": "feature/old",
                    "body": "Closes #456",
                    "mergedAt": "2024-01-09T12:00:00Z",
                    "issue": 456,
                }
            },
        }
    )

    # Mock client with new PRs
    mock_client = MockGitHubClient(
        [
            {
                "number": 100,
                "headRefName": "feature/old",
                "body": "Closes #456",
                "mergedAt": "2024-01-09T12:00:00Z",
            },
            {
                "number": 101,
                "headRefName": "feature/new",
                "body": "Fixes #789",
                "mergedAt": "2024-01-15T12:00:00Z",
            },
        ]
    )

    new_count = cache.sync(mock_client, limit=200)

    assert new_count == 1  # Only the new one
    loaded = cache._load_cache()
    assert "100" in loaded["prs"]
    assert "101" in loaded["prs"]
    assert loaded["prs"]["100"]["issue"] == 456
    assert loaded["prs"]["101"]["issue"] == 789


def test_sync_no_duplicates(cache: MergedPRCache) -> None:
    """sync() does not duplicate already-cached PRs."""
    # Pre-populate cache
    cache._save_cache(
        {
            "last_sync": "2024-01-10T10:00:00Z",
            "prs": {
                "100": {
                    "number": 100,
                    "headRefName": "feature/old",
                    "body": "Closes #456",
                    "mergedAt": "2024-01-09T12:00:00Z",
                    "issue": 456,
                }
            },
        }
    )

    # Mock client with same PR
    mock_client = MockGitHubClient(
        [
            {
                "number": 100,
                "headRefName": "feature/old",
                "body": "Closes #456",
                "mergedAt": "2024-01-09T12:00:00Z",
            },
        ]
    )

    new_count = cache.sync(mock_client)

    assert new_count == 0  # No new PRs
    loaded = cache._load_cache()
    assert len(loaded["prs"]) == 1


def test_rebuild_replaces_cache(cache: MergedPRCache) -> None:
    """rebuild() clears old entries and writes fresh data."""
    # Pre-populate cache with old data
    cache._save_cache(
        {
            "last_sync": "2024-01-01T10:00:00Z",
            "prs": {
                "50": {
                    "number": 50,
                    "headRefName": "feature/old",
                    "body": "Closes #123",
                    "mergedAt": "2023-12-01T12:00:00Z",
                    "issue": 123,
                }
            },
        }
    )

    # Mock client with new data
    mock_client = MockGitHubClient(
        [
            {
                "number": 100,
                "headRefName": "feature/new",
                "body": "Closes #456",
                "mergedAt": "2024-01-15T12:00:00Z",
            },
            {
                "number": 101,
                "headRefName": "feature/another",
                "body": "Fixes #789",
                "mergedAt": "2024-01-16T12:00:00Z",
            },
        ]
    )

    count = cache.rebuild(mock_client)

    assert count == 2
    loaded = cache._load_cache()
    assert "50" not in loaded["prs"]  # Old entry removed
    assert "100" in loaded["prs"]
    assert "101" in loaded["prs"]
    assert loaded["prs"]["100"]["issue"] == 456
    assert loaded["prs"]["101"]["issue"] == 789


def test_sync_handles_prs_without_linked_issues(cache: MergedPRCache) -> None:
    """sync() skips PRs that don't close any issues."""
    mock_client = MockGitHubClient(
        [
            {
                "number": 100,
                "headRefName": "feature/orphan",
                "body": "No closing keywords here",
                "mergedAt": "2024-01-15T12:00:00Z",
            },
            {
                "number": 101,
                "headRefName": "feature/linked",
                "body": "Closes #456",
                "mergedAt": "2024-01-16T12:00:00Z",
            },
        ]
    )

    new_count = cache.sync(mock_client)

    assert new_count == 1  # Only the linked one
    loaded = cache._load_cache()
    assert "100" not in loaded["prs"]
    assert "101" in loaded["prs"]


def test_rebuild_with_unlimited_fetch(cache: MergedPRCache) -> None:
    """rebuild() passes limit=None to fetch all PRs."""
    # Create mock client with many PRs
    all_prs = [
        {
            "number": i,
            "headRefName": f"feature/{i}",
            "body": f"Closes #{i * 10}",
            "mergedAt": f"2024-01-{i:02d}T12:00:00Z",
        }
        for i in range(1, 51)
    ]
    mock_client = MockGitHubClient(all_prs)

    count = cache.rebuild(mock_client)

    assert count == 50  # All 50 PRs processed
    loaded = cache._load_cache()
    assert len(loaded["prs"]) == 50


def test_cache_returns_normalized_dict_structure(cache: MergedPRCache) -> None:
    """Cache returns dict with GitHub API keys: headRefName, body, mergedAt."""
    test_data = {
        "last_sync": "2024-01-15T10:00:00Z",
        "prs": {
            "100": {
                "number": 100,
                "headRefName": "feature/test",
                "body": "Closes #456",
                "mergedAt": "2024-01-10T12:00:00Z",
                "issue": 456,
            }
        },
    }
    cache._save_cache(test_data)

    result = cache.get_merged_pr_for_issue(456)
    assert result is not None
    # Verify all GitHub API keys are present
    assert "number" in result
    assert "headRefName" in result
    assert "body" in result
    assert "mergedAt" in result
    assert "issue" in result
    assert result["number"] == 100
    assert result["headRefName"] == "feature/test"
    assert result["body"] == "Closes #456"
    assert result["mergedAt"] == "2024-01-10T12:00:00Z"
    assert result["issue"] == 456
