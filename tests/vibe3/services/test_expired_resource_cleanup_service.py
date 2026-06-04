"""Tests for ExpiredResourceCleanupService."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.protocols import BackendProtocol
from vibe3.services.expired_resource_cleanup_service import (
    ExpiredResourceCleanupService,
)


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    """Create a mock GitClient."""
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test-branch"
    client._run.return_value = "/path/to/.git"
    return client


def test_expired_resource_service_accepts_backend():
    """ExpiredResourceCleanupService should accept BackendProtocol."""
    mock_backend = MagicMock(spec=BackendProtocol)
    mock_store = MagicMock(spec=SQLiteClient)
    mock_git_client = MagicMock(spec=GitClient)

    service = ExpiredResourceCleanupService(
        store=mock_store,
        git_client=mock_git_client,
        backend=mock_backend,
    )

    assert service._backend is mock_backend


def test_clean_expired_local_branches_deletes_old(mock_store, mock_git_client) -> None:
    """Delete local branches older than max age, excluding protected and current."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    recent_date = (datetime.now() - timedelta(days=3)).strftime(
        "%Y-%m-%d %H:%M:%S +0800"
    )

    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-old", "timestamp": old_date},
        {"branch": "feature-recent", "timestamp": recent_date},
        {"branch": "main", "timestamp": old_date},  # Protected
        {"branch": "current-branch", "timestamp": old_date},  # Current
    ]

    mock_git_client.get_current_branch.return_value = "current-branch"
    mock_git_client.branch_exists.return_value = True

    # Mock worktree check
    mock_git_client.is_branch_occupied_by_worktree.return_value = False
    mock_git_client.find_worktree_path_for_branch.return_value = None

    result = service.clean_expired_local_branches(max_age_days=7)

    # Verify: only feature-old deleted
    assert "cleaned" in result
    assert "feature-old" in result["cleaned"]
    assert "main" not in result["cleaned"]
    assert "current-branch" not in result["cleaned"]
    assert "feature-recent" not in result["cleaned"]


def test_clean_expired_remote_branches_parses_non_0800_offsets(
    mock_store, mock_git_client
) -> None:
    """Remote cleanup should handle git timestamps with or without timezone colon."""
    github_client = MagicMock()
    # Mock pr_service to avoid real GitHub API calls and cache I/O
    pr_service = MagicMock()
    pr_service.refresh_open_pr_cache.return_value = []

    service = ExpiredResourceCleanupService(
        store=mock_store,
        git_client=mock_git_client,
        github_client=github_client,
        pr_service=pr_service,
    )

    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
        "%Y-%m-%d %H:%M:%S +0000"
    )
    old_date_with_colon = old_date[:-2] + ":" + old_date[-2:]
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "origin/feature-old", "timestamp": old_date},
        {"branch": "origin/feature-colon", "timestamp": old_date_with_colon},
    ]

    result = service.clean_expired_remote_branches(max_age_days=7)

    assert result["cleaned"] == ["origin/feature-old", "origin/feature-colon"]
    mock_git_client.delete_remote_branch.assert_any_call("feature-old")
    mock_git_client.delete_remote_branch.assert_any_call("feature-colon")


def test_clean_expired_local_branches_reports_worktree_removal(
    mock_store, mock_git_client
) -> None:
    """When a local branch has a worktree, record it in skipped_worktree."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-old", "timestamp": old_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_git_client.branch_exists.return_value = True

    mock_git_client.is_branch_occupied_by_worktree.return_value = True
    mock_git_client.find_worktree_path_for_branch.return_value = Path("/tmp/wt")

    with patch("vibe3.services.expired_resource_cleanup_service.remove_worktree") as rm:
        result = service.clean_expired_local_branches(max_age_days=7)

    rm.assert_called_once()
    assert "feature-old" in result["skipped_worktree"]
    assert "feature-old" in result["cleaned"]


def test_clean_expired_local_branches_skips_active_flow(
    mock_store, mock_git_client
) -> None:
    """Branches with an active flow record must be protected from cleanup."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "dev/issue-active", "timestamp": old_date},
        {"branch": "dev/issue-abandoned", "timestamp": old_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_git_client.branch_exists.return_value = True
    mock_git_client.is_branch_occupied_by_worktree.return_value = False
    mock_store.get_all_flows.return_value = [
        {"branch": "dev/issue-active", "flow_status": "active"},
    ]

    result = service.clean_expired_local_branches(max_age_days=7)

    # Active flow branch protected; abandoned (no flow record) cleaned
    assert "dev/issue-active" in result["skipped_active_flow"]
    assert "dev/issue-active" not in result["cleaned"]
    assert "dev/issue-abandoned" in result["cleaned"]


def test_clean_expired_local_branches_skips_blocked_flow(
    mock_store, mock_git_client
) -> None:
    """Branches with a blocked flow record must be protected from cleanup."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "dev/issue-blocked", "timestamp": old_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_git_client.branch_exists.return_value = True
    mock_git_client.is_branch_occupied_by_worktree.return_value = False
    mock_store.get_all_flows.return_value = [
        {"branch": "dev/issue-blocked", "flow_status": "blocked"},
    ]

    result = service.clean_expired_local_branches(max_age_days=7)

    assert "dev/issue-blocked" in result["skipped_active_flow"]
    assert "dev/issue-blocked" not in result["cleaned"]


def test_clean_expired_local_branches_force_deletes_regardless_of_merge(
    mock_store, mock_git_client
) -> None:
    """Abandoned stale branches are force-deleted (git branch -D), ignoring merge."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-unmerged", "timestamp": old_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_git_client.branch_exists.return_value = True
    mock_git_client.is_branch_occupied_by_worktree.return_value = False
    mock_store.get_all_flows.return_value = []

    result = service.clean_expired_local_branches(max_age_days=7)

    assert "feature-unmerged" in result["cleaned"]
    mock_git_client.delete_branch.assert_called_once_with(
        "feature-unmerged", force=True
    )


def test_clean_expired_local_branches_force_flag_bypasses_age(
    mock_store, mock_git_client
) -> None:
    """force=True deletes eligible branches regardless of age."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    recent_date = (datetime.now() - timedelta(days=2)).strftime(
        "%Y-%m-%d %H:%M:%S +0800"
    )
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-recent-abandoned", "timestamp": recent_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_git_client.branch_exists.return_value = True
    mock_git_client.is_branch_occupied_by_worktree.return_value = False
    mock_store.get_all_flows.return_value = []

    # Without force: recent branch skipped by age gate
    res_default = service.clean_expired_local_branches(max_age_days=7, force=False)
    assert "feature-recent-abandoned" not in res_default["cleaned"]

    # With force: age gate bypassed, branch deleted
    res_force = service.clean_expired_local_branches(max_age_days=7, force=True)
    assert "feature-recent-abandoned" in res_force["cleaned"]


def test_clean_expired_local_branches_aborts_when_flow_query_fails(
    mock_store, mock_git_client
) -> None:
    """If flow records cannot be loaded, cleanup aborts (no destructive deletes)."""
    service = ExpiredResourceCleanupService(
        store=mock_store, git_client=mock_git_client
    )

    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    mock_git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-old", "timestamp": old_date},
    ]
    mock_git_client.get_current_branch.return_value = "main"
    mock_store.get_all_flows.side_effect = RuntimeError("db locked")

    result = service.clean_expired_local_branches(max_age_days=7)

    assert result["cleaned"] == []
    assert result["failed"]
    mock_git_client.delete_branch.assert_not_called()
