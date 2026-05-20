"""Tests for check_cleanup_service with live session filtering."""

from unittest.mock import MagicMock, patch

from vibe3.services.check_cleanup_service import CheckCleanupService
from vibe3.services.expired_resource_cleanup_service import (
    ExpiredResourceCleanupService,
)


def test_clean_residual_branches_filters_live_sessions_before_cleanup() -> None:
    """Live session branches should be skipped before cleanup attempts."""
    store = MagicMock()
    git_client = MagicMock()

    # Mock terminal flows
    store.get_all_flows.return_value = [
        {
            "branch": "task/issue-123",
            "flow_status": "aborted",
        },
        {
            "branch": "task/issue-456",
            "flow_status": "done",
        },
        {
            "branch": "task/issue-789",
            "flow_status": "aborted",
        },
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: issue-123 and issue-789 have live sessions
    with patch.object(
        service,
        "_get_branches_with_live_sessions",
        return_value={"task/issue-123", "task/issue-789"},
    ):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # Verify: only issue-456 was processed (no live session)
            assert mock_process.call_count == 1
            mock_process.assert_called_once()

            # Verify result structure
            assert "skipped_live" in result
            assert set(result["skipped_live"]) == {
                "task/issue-123",
                "task/issue-789",
            }
            assert "task/issue-456" not in result["skipped_live"]


def test_clean_residual_branches_logs_skipped_branches() -> None:
    """Should log which branches were skipped due to live sessions."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "aborted"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend"),
        patch("vibe3.environment.session_registry.SessionRegistryService") as registry,
    ):
        registry.return_value._store.list_live_runtime_sessions.return_value = [
            {
                "branch": "task/issue-123",
                "tmux_session": "vibe3-run-issue-123",
            },
        ]

        # Mock backend to say issue-123 has live session
        with patch.object(service, "_get_branches_with_live_sessions") as mock_get_live:
            mock_get_live.return_value = {"task/issue-123"}

            with patch.object(service, "_process_terminal_flow"):
                result = service.clean_residual_branches()

                # Verify summary includes skipped count
                assert "skipped 1 branches with live sessions" in str(result["summary"])


def test_get_branches_with_live_sessions_queries_once() -> None:
    """Should query live sessions only once, not per branch."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend"),
        patch(
            "vibe3.environment.session_registry.SessionRegistryService"
        ) as registry_cls,
    ):
        registry = registry_cls.return_value
        # Mock the new method
        registry.get_all_branches_with_live_sessions.return_value = {
            "task/issue-123",
            "task/issue-456",
        }

        result = service._get_branches_with_live_sessions()

        # Verify: called once, not per branch
        registry.get_all_branches_with_live_sessions.assert_called_once()

        # Verify: both branches returned
        assert result == {"task/issue-123", "task/issue-456"}


def test_clean_residual_branches_handles_no_live_sessions() -> None:
    """Should work correctly when no live sessions exist."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "done"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: no live sessions
    with patch.object(service, "_get_branches_with_live_sessions", return_value=set()):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # All flows should be processed
            assert mock_process.call_count == 2
            assert result["skipped_live"] == []


def test_clean_expired_local_branches_deletes_old() -> None:
    """Delete local branches older than max age, excluding protected and current."""
    from datetime import datetime, timedelta

    store = MagicMock()
    git_client = MagicMock()
    service = ExpiredResourceCleanupService(store=store, git_client=git_client)

    # Mock git_client
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    recent_date = (datetime.now() - timedelta(days=3)).strftime(
        "%Y-%m-%d %H:%M:%S +0800"
    )

    git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "feature-old", "timestamp": old_date},
        {"branch": "feature-recent", "timestamp": recent_date},
        {"branch": "main", "timestamp": old_date},  # Protected
        {"branch": "current-branch", "timestamp": old_date},  # Current
    ]

    git_client.get_current_branch.return_value = "current-branch"
    git_client.branch_exists.return_value = True

    # Mock worktree check
    git_client.is_branch_occupied_by_worktree.return_value = False
    git_client.find_worktree_path_for_branch.return_value = None

    result = service.clean_expired_local_branches(max_age_days=7)

    # Verify: only feature-old deleted
    assert "cleaned" in result
    assert "feature-old" in result["cleaned"]
    assert "main" not in result["cleaned"]
    assert "current-branch" not in result["cleaned"]
    assert "feature-recent" not in result["cleaned"]


def test_clean_expired_remote_branches_parses_non_0800_offsets() -> None:
    """Remote cleanup should handle git timestamps with or without timezone colon."""
    from datetime import datetime, timedelta, timezone

    store = MagicMock()
    git_client = MagicMock()
    github_client = MagicMock()
    service = ExpiredResourceCleanupService(
        store=store, git_client=git_client, github_client=github_client
    )

    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
        "%Y-%m-%d %H:%M:%S +0000"
    )
    old_date_with_colon = old_date[:-2] + ":" + old_date[-2:]
    git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "origin/feature-old", "timestamp": old_date},
        {"branch": "origin/feature-colon", "timestamp": old_date_with_colon},
    ]
    github_client.list_all_prs.return_value = []

    result = service.clean_expired_remote_branches(max_age_days=7)

    assert result["cleaned"] == ["origin/feature-old", "origin/feature-colon"]
    git_client.delete_remote_branch.assert_any_call("feature-old")
    git_client.delete_remote_branch.assert_any_call("feature-colon")


def test_clean_residual_branches_integrates_all_cleanups() -> None:
    """Should call all cleanup methods when enabled."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock all dependencies
    store.get_all_flows.return_value = []
    git_client.get_current_branch.return_value = "main"

    with patch.object(
        ExpiredResourceCleanupService, "clean_expired_agent_worktrees"
    ) as mock_agent:
        with patch.object(
            ExpiredResourceCleanupService, "clean_expired_remote_branches"
        ) as mock_remote:
            with patch.object(
                ExpiredResourceCleanupService, "clean_expired_local_branches"
            ) as mock_local:
                mock_agent.return_value = {"cleaned": ["agent-old"]}
                mock_remote.return_value = {"cleaned": ["origin/feature-old"]}
                mock_local.return_value = {"cleaned": ["feature-old"]}

                result = service.clean_residual_branches()

                # Verify all called
                mock_agent.assert_called_once()
                mock_remote.assert_called_once()
                mock_local.assert_called_once()

                # Verify results include all sections
                assert "agent_worktrees" in result
                assert "remote_branches" in result
                assert "local_branches" in result
