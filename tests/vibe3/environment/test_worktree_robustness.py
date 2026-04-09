"""Tests for WorktreeManager robustness features - prune and orphan cleanup."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from vibe3.environment.worktree import WorktreeManager
from vibe3.models.orchestra_config import OrchestraConfig


def make_config() -> OrchestraConfig:
    """Create a minimal config for testing."""
    return OrchestraConfig()


class TestWorktreePrune:
    """Tests for git worktree prune behavior."""

    def test_create_issue_worktree_calls_prune(self, tmp_path: Path) -> None:
        """WorktreeManager calls git worktree prune before creating issue worktree."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-branch"
        issue_number = 123

        # Mock git worktree commands
        with patch("subprocess.run") as mock_run:
            # Setup: branch not found, prune succeeds, worktree add succeeds
            mock_run.side_effect = [
                # _find_worktree_for_branch (no existing worktree)
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list", "--porcelain"],
                    returncode=0,
                    stdout="",  # No worktrees for this branch
                    stderr="",
                ),
                # prune in _create_issue_worktree
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # _find_worktree_by_path (no existing worktree)
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # git worktree add
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            manager.acquire_issue_worktree(issue_number, branch)

        # Verify prune was called
        prune_calls = [
            call
            for call in mock_run.call_args_list
            if call[0][0][:3] == ["git", "worktree", "prune"]
        ]
        assert len(prune_calls) >= 1

    def test_create_temporary_worktree_calls_prune(self, tmp_path: Path) -> None:
        """WorktreeManager calls git worktree prune before creating temp worktree."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        issue_number = 456
        base_branch = "main"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add", "--detach"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            manager.acquire_temporary_worktree(issue_number, base_branch)

        # Verify prune was called
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0][:3] == ["git", "worktree", "prune"]

    def test_prune_continues_on_error(self, tmp_path: Path) -> None:
        """WorktreeManager should continue even if prune fails."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-prune-fail"
        issue_number = 789

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # Prune fails
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=1,
                    stdout="",
                    stderr="error",
                ),
                # Worktree add still proceeds and succeeds
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            # Should not raise
            result = manager.acquire_issue_worktree(issue_number, branch)
            assert result.issue_number == issue_number


class TestOrphanDirectoryCleanup:
    """Tests for orphan directory cleanup behavior."""

    def test_create_deletes_unregistered_existing_directory(
        self, tmp_path: Path
    ) -> None:
        """WorktreeManager should delete unregistered directory at target path."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-orphan"
        issue_number = 111
        wt_path = tmp_path / ".worktrees" / branch

        # Create orphan directory (not in git worktree list)
        wt_path.mkdir(parents=True)
        (wt_path / "stale_file.txt").write_text("stale content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # _find_worktree_for_branch (no existing worktree)
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list", "--porcelain"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # Prune
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # _find_worktree_by_path returns False (not registered)
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list"],
                    returncode=0,
                    stdout="worktree /other/path\n",  # Different worktree
                    stderr="",
                ),
                # git worktree add succeeds
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            manager.acquire_issue_worktree(issue_number, branch)

        # Verify orphan directory was deleted
        assert not (wt_path / "stale_file.txt").exists()

    def test_create_preserves_registered_existing_directory(
        self, tmp_path: Path
    ) -> None:
        """WorktreeManager should reuse existing registered worktree."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-registered"
        issue_number = 222
        wt_path = tmp_path / ".worktrees" / branch

        # Create directory
        wt_path.mkdir(parents=True)
        (wt_path / "existing_file.txt").write_text("existing content")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # _find_worktree_for_branch finds existing worktree
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list", "--porcelain"],
                    returncode=0,
                    stdout=f"worktree {wt_path}\nbranch refs/heads/{branch}\n",
                    stderr="",
                ),
            ]

            result = manager.acquire_issue_worktree(issue_number, branch)

        # Verify reused existing worktree
        assert result.path == wt_path
        assert result.branch == branch
        assert result.issue_number == issue_number
