"""Tests for WorktreeCleanupService."""

from pathlib import Path
from unittest.mock import patch

from vibe3.models.orchestra_config import OrchestraConfig, WorktreeCleanupConfig
from vibe3.orchestra.services.worktree_cleanup import (
    CleanupDecision,
    CleanupResult,
    WorktreeCleanupService,
    WorktreeInfo,
    assess_worktree,
    execute_cleanup,
    find_worktrees_for_pr_branch,
    list_do_worktrees,
)
from vibe3.runtime.service_protocol import GitHubEvent


def _config(**kwargs) -> WorktreeCleanupConfig:
    """Create a cleanup config with defaults."""
    return WorktreeCleanupConfig(**kwargs)


def _worktree(
    path: str = "/tmp/do-20260430-abc123",
    branch: str = "task/issue-123",
    mtime: float = 0.0,
) -> WorktreeInfo:
    """Create a worktree info struct."""
    return WorktreeInfo(path=Path(path), branch=branch, mtime=mtime)


def test_list_do_worktrees_filters_correctly() -> None:
    """Test that only do-* worktrees are returned."""
    porcelain_output = """worktree /tmp/main
branch main

worktree /tmp/do-20260430-abc123
branch task/issue-123

worktree /tmp/task/issue-456
branch task/issue-456

worktree /tmp/do-20260429-def456
branch task/issue-789
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = porcelain_output

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_mtime = 1000.0

            result = list_do_worktrees(Path("/tmp/main"))

            # Should only return do-* worktrees
            assert len(result) == 2
            assert result[0].path.name == "do-20260430-abc123"
            assert result[1].path.name == "do-20260429-def456"


def test_list_do_worktrees_empty() -> None:
    """Test empty result when no do-* worktrees exist."""
    porcelain_output = """worktree /tmp/main
branch main

worktree /tmp/task/issue-456
branch task/issue-456
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = porcelain_output

        result = list_do_worktrees(Path("/tmp/main"))

        assert len(result) == 0


def test_assess_clean_worktree() -> None:
    """Test that a clean worktree past TTL returns CLEAN."""
    wt = _worktree(mtime=0.0)  # Very old
    config = _config(ttl_hours=1)

    with patch("subprocess.run") as mock_run:
        # Mock git status (clean)
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        # Mock tmux (no sessions)
        with patch(
            "vibe3.orchestra.services.worktree_cleanup.time", return_value=10000.0
        ):
            result = assess_worktree(wt, config)
            assert result == CleanupDecision.CLEAN


def test_assess_skip_dirty() -> None:
    """Test that a dirty worktree returns SKIP_DIRTY."""
    wt = _worktree(mtime=0.0)
    config = _config(ttl_hours=1)

    with patch("subprocess.run") as mock_run:
        # Mock git status (dirty)
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "M file.py\n"

        result = assess_worktree(wt, config)
        assert result == CleanupDecision.SKIP_DIRTY


def test_assess_skip_ttl_not_expired() -> None:
    """Test that a recent worktree returns SKIP_TTL_NOT_EXPIRED."""
    current_time = 10000.0
    wt = _worktree(mtime=9900.0)  # 100 seconds ago
    config = _config(ttl_hours=1)  # 3600 seconds TTL

    # Mock time in the correct namespace
    with patch(
        "vibe3.orchestra.services.worktree_cleanup.time", return_value=current_time
    ):
        with patch("subprocess.run") as mock_run:
            # Mock git status (clean)
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""

            result = assess_worktree(wt, config)
            assert result == CleanupDecision.SKIP_TTL_NOT_EXPIRED


def test_assess_skip_active_tmux() -> None:
    """Test that a worktree with active tmux session returns SKIP_ACTIVE_SESSION."""
    wt = _worktree(mtime=0.0)
    config = _config(ttl_hours=1)

    def mock_run_side_effect(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = ""

        # Tmux command returns active session
        if cmd[0] == "tmux":
            result = MockResult()
            result.stdout = f"session1:{wt.path}"
            return result

        # Git status (clean)
        if cmd[0] == "git" and cmd[1] == "status":
            return MockResult()

        return MockResult()

    with patch("vibe3.orchestra.services.worktree_cleanup.time", return_value=10000.0):
        with patch("subprocess.run", side_effect=mock_run_side_effect):
            result = assess_worktree(wt, config)
            assert result == CleanupDecision.SKIP_ACTIVE_SESSION


def test_assess_skip_not_do_pattern() -> None:
    """Test that a non-do-* worktree returns SKIP_NOT_DO_PATTERN."""
    wt = WorktreeInfo(
        path=Path("/tmp/task-issue-123"), branch="task/issue-123", mtime=0.0
    )
    config = _config(ttl_hours=1)

    result = assess_worktree(wt, config)
    assert result == CleanupDecision.SKIP_NOT_DO_PATTERN


def test_execute_cleanup_dry_run() -> None:
    """Test that dry_run=True logs decisions without removing."""
    worktrees = [_worktree()]
    repo_path = Path("/tmp/main")

    with patch("subprocess.run") as mock_run:
        results = execute_cleanup(worktrees, dry_run=True, repo_path=repo_path)

        assert len(results) == 1
        assert results[0].success
        assert results[0].reason == "dry_run"
        # Should not call git worktree remove
        assert not any(
            call[0][0] == "git" and "worktree" in call[0] and "remove" in call[0]
            for call in mock_run.call_args_list
        )


def test_execute_cleanup_real() -> None:
    """Test that dry_run=False calls git worktree remove."""
    worktrees = [_worktree()]
    repo_path = Path("/tmp/main")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        with patch.object(Path, "exists", return_value=False):
            results = execute_cleanup(worktrees, dry_run=False, repo_path=repo_path)

            assert len(results) == 1
            assert results[0].success
            assert results[0].reason == "git_remove"

            # Should call git worktree remove
            calls = [str(call) for call in mock_run.call_args_list]
            assert any("worktree" in call and "remove" in call for call in calls)


def test_find_worktrees_for_pr_branch() -> None:
    """Test that worktrees matching PR branch are returned."""
    porcelain_output = """worktree /tmp/do-20260430-abc123
branch task/issue-123

worktree /tmp/do-20260429-def456
branch task/issue-456
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = porcelain_output

        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_mtime = 1000.0

            result = find_worktrees_for_pr_branch(Path("/tmp/main"), "task/issue-123")

            assert len(result) == 1
            assert result[0].branch == "task/issue-123"


def test_handle_event_ignores_non_closed_pr() -> None:
    """Test that non-closed PR events are no-ops."""
    config = OrchestraConfig(polling_interval=900)
    svc = WorktreeCleanupService(config)

    event = GitHubEvent(
        event_type="pull_request",
        action="opened",
        payload={"pull_request": {"head": {"ref": "task/issue-123"}}},
        source="webhook",
    )

    with patch(
        "vibe3.orchestra.services.worktree_cleanup.find_worktrees_for_pr_branch"
    ) as mock_find:
        import asyncio

        asyncio.run(svc.handle_event(event))
        mock_find.assert_not_called()


def test_handle_event_pr_closed_triggers_cleanup() -> None:
    """Test that PR closed event triggers cleanup for matching branch."""
    config = OrchestraConfig(polling_interval=900)
    svc = WorktreeCleanupService(config)

    event = GitHubEvent(
        event_type="pull_request",
        action="closed",
        payload={"pull_request": {"head": {"ref": "task/issue-123"}}},
        source="webhook",
    )

    wt = _worktree(branch="task/issue-123")

    with patch(
        "vibe3.orchestra.services.worktree_cleanup.find_worktrees_for_pr_branch",
        return_value=[wt],
    ):
        with patch(
            "vibe3.orchestra.services.worktree_cleanup.execute_cleanup",
            return_value=[CleanupResult(path=wt.path, success=True, reason="test")],
        ):
            import asyncio

            asyncio.run(svc.handle_event(event))
            # Should complete without error


def test_on_tick_ttl_gc() -> None:
    """Test that periodic tick triggers TTL-based GC."""
    config = OrchestraConfig(polling_interval=900)
    svc = WorktreeCleanupService(config)

    wt = _worktree(mtime=0.0)

    # Advance tick counter to trigger GC (every 4 ticks)
    svc._tick_counter = 3

    with patch(
        "vibe3.orchestra.services.worktree_cleanup.list_do_worktrees",
        return_value=[wt],
    ):
        with patch(
            "vibe3.orchestra.services.worktree_cleanup.assess_worktree",
            return_value=CleanupDecision.CLEAN,
        ):
            with patch(
                "vibe3.orchestra.services.worktree_cleanup.execute_cleanup",
                return_value=[CleanupResult(path=wt.path, success=True, reason="test")],
            ):
                import asyncio

                asyncio.run(svc.on_tick())
                # Should increment tick counter
                assert svc._tick_counter == 4


def test_on_tick_skips_when_not_enabled() -> None:
    """Test that on_tick is a no-op when cleanup is disabled."""
    config = OrchestraConfig(
        polling_interval=900, cleanup=WorktreeCleanupConfig(enabled=False)
    )
    svc = WorktreeCleanupService(config)

    with patch(
        "vibe3.orchestra.services.worktree_cleanup.list_do_worktrees"
    ) as mock_list:
        import asyncio

        asyncio.run(svc.on_tick())
        mock_list.assert_not_called()
