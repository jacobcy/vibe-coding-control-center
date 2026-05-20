"""Tests for check_cleanup_service with live session filtering."""

from unittest.mock import MagicMock, patch

from vibe3.services.check_cleanup_service import CheckCleanupService


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


def test_clean_expired_agent_worktrees_removes_old_worktrees() -> None:
    """Expired agent worktrees without live sessions should be removed via git."""
    import os
    import tempfile
    from datetime import datetime, timedelta
    from pathlib import Path

    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    # No live sessions for any worktree
    store.list_live_sessions_by_worktree.return_value = []

    with tempfile.TemporaryDirectory() as tmpdir:
        old_worktree = Path(tmpdir) / "agent-old123"
        old_worktree.mkdir()
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_worktree, (old_time.timestamp(), old_time.timestamp()))

        recent_worktree = Path(tmpdir) / "agent-recent456"
        recent_worktree.mkdir()

        with patch.object(
            service, "_get_agent_worktree_base", return_value=Path(tmpdir)
        ):
            with patch(
                "vibe3.services.check_cleanup_service.remove_worktree"
            ) as mock_remove:
                result = service._clean_expired_agent_worktrees(max_age_days=7)

                # Old worktree should be removed via remove_worktree
                mock_remove.assert_called_once_with(old_worktree, force=True)

                # Recent worktree should NOT be removed
                assert recent_worktree.exists()
                assert "cleaned" in result
                assert len(result["cleaned"]) == 1
                assert "agent-old123" in result["cleaned"]


def test_clean_expired_agent_worktrees_skips_live_sessions() -> None:
    """Expired worktrees with live sessions should be skipped, not removed."""
    import os
    import tempfile
    from datetime import datetime, timedelta
    from pathlib import Path

    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    with tempfile.TemporaryDirectory() as tmpdir:
        old_worktree = Path(tmpdir) / "agent-old123"
        old_worktree.mkdir()
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_worktree, (old_time.timestamp(), old_time.timestamp()))

        # Resolved absolute path used for lookup
        resolved_path = str(old_worktree.resolve())

        def mock_list_live(worktree_path: str) -> list[dict]:
            if worktree_path == resolved_path:
                return [{"id": 1, "status": "running", "role": "executor"}]
            return []

        store.list_live_sessions_by_worktree.side_effect = mock_list_live

        with patch.object(
            service, "_get_agent_worktree_base", return_value=Path(tmpdir)
        ):
            with patch(
                "vibe3.services.check_cleanup_service.remove_worktree"
            ) as mock_remove:
                result = service._clean_expired_agent_worktrees(max_age_days=7)

                # Should NOT call remove_worktree - worktree has live sessions
                mock_remove.assert_not_called()

                assert result["skipped_live"] == ["agent-old123"]
                assert result["cleaned"] == []
                assert old_worktree.exists()


def test_clean_expired_agent_worktrees_handles_git_error() -> None:
    """Failed git worktree removal should be recorded as failure."""
    import os
    import tempfile
    from datetime import datetime, timedelta
    from pathlib import Path

    from vibe3.exceptions import GitError

    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    store.list_live_sessions_by_worktree.return_value = []

    with tempfile.TemporaryDirectory() as tmpdir:
        old_worktree = Path(tmpdir) / "agent-old123"
        old_worktree.mkdir()
        old_time = datetime.now() - timedelta(days=10)
        os.utime(old_worktree, (old_time.timestamp(), old_time.timestamp()))

        with patch.object(
            service, "_get_agent_worktree_base", return_value=Path(tmpdir)
        ):
            with patch(
                "vibe3.services.check_cleanup_service.remove_worktree",
                side_effect=GitError("worktree remove", "test error"),
            ):
                result = service._clean_expired_agent_worktrees(max_age_days=7)

                assert result["cleaned"] == []
                assert len(result["failed"]) == 1
                assert "agent-old123" in result["failed"][0]
                assert "test error" in result["failed"][0]


def test_clean_expired_remote_branches_deletes_old() -> None:
    """Delete remote branches older than max age, excluding protected."""
    from datetime import datetime, timedelta

    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock git_client.get_all_branches_with_timestamps
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S +0800")
    recent_date = (datetime.now() - timedelta(days=3)).strftime(
        "%Y-%m-%d %H:%M:%S +0800"
    )

    git_client.get_all_branches_with_timestamps.return_value = [
        {"branch": "origin/feature-old", "timestamp": old_date},
        {"branch": "origin/feature-recent", "timestamp": recent_date},
        {"branch": "origin/main", "timestamp": old_date},  # Protected, skip
    ]

    # Mock GitHub PR check
    github_client = MagicMock()
    github_client.list_all_prs.return_value = []  # No open PRs
    service._github_client = github_client

    result = service._clean_expired_remote_branches(max_age_days=7)

    # Verify: only feature-old deleted, feature-recent kept, main skipped
    assert "cleaned" in result
    assert "origin/feature-old" in result["cleaned"]
    assert "origin/main" not in result["cleaned"]
    assert "origin/feature-recent" not in result["cleaned"]
