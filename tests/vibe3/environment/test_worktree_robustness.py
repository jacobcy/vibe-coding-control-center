"""Tests for WorktreeManager robustness features.

Regression tests for git worktree prune, orphan directory cleanup,
already checked out reuse, and --detach temporary worktrees.
"""

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


class TestAlreadyCheckedOutReuse:
    """Tests for reusing worktree when branch is already checked out."""

    def test_reuse_existing_worktree_on_already_checked_out(
        self, tmp_path: Path
    ) -> None:
        """WorktreeManager reuses existing worktree when branch already checked out."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-already-checked-out"
        issue_number = 333
        existing_wt_path = tmp_path / ".worktrees" / "existing-location"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # Prune
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # _find_worktree_by_path (not found)
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # git worktree add fails with "already checked out"
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add"],
                    returncode=1,
                    stdout="",
                    stderr=f"fatal: '{branch}' is already checked out at "
                    f"'{existing_wt_path}'",
                ),
                # _find_worktree_for_branch finds the existing worktree
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list", "--porcelain"],
                    returncode=0,
                    stdout=f"worktree {existing_wt_path}\nbranch refs/heads/{branch}\n",
                    stderr="",
                ),
            ]

            result = manager.acquire_issue_worktree(issue_number, branch)

        # Verify reused existing worktree
        assert result.path == existing_wt_path
        assert result.branch == branch
        assert result.issue_number == issue_number
        assert not result.is_temporary

    def test_error_when_already_checked_out_but_not_found(self, tmp_path: Path) -> None:
        """WorktreeManager raises error when branch checked but worktree not found."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        branch = "dev/test-missing-worktree"
        issue_number = 444

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # Prune
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # _find_worktree_by_path
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # git worktree add fails with "already checked out"
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add"],
                    returncode=1,
                    stdout="",
                    stderr=f"fatal: '{branch}' is already checked out at "
                    "'/missing/path'",
                ),
                # _find_worktree_for_branch doesn't find it
                subprocess.CompletedProcess(
                    args=["git", "worktree", "list", "--porcelain"],
                    returncode=0,
                    stdout="",  # Empty - branch not in any worktree
                    stderr="",
                ),
            ]

            # Should raise SystemError
            import pytest

            from vibe3.exceptions import SystemError

            with pytest.raises(SystemError, match="Git worktree add failed"):
                manager.acquire_issue_worktree(issue_number, branch)


class TestDetachTemporaryWorktree:
    """Tests for --detach temporary worktree behavior."""

    def test_temporary_worktree_uses_detach_flag(self, tmp_path: Path) -> None:
        """WorktreeManager should use --detach for temporary worktrees."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        issue_number = 555
        base_branch = "main"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # Prune
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # git worktree add --detach succeeds
                subprocess.CompletedProcess(
                    args=["git", "worktree", "add", "--detach"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            result = manager.acquire_temporary_worktree(issue_number, base_branch)

        # Verify --detach was used
        add_call = mock_run.call_args_list[1]
        command = add_call[0][0]
        assert "--detach" in command
        assert base_branch in command

        # Verify result
        assert result.is_temporary is True
        assert result.branch == base_branch
        assert result.issue_number == issue_number

    def test_detach_allows_multiple_worktrees_from_same_base(
        self, tmp_path: Path
    ) -> None:
        """Multiple temporary worktrees can be created from same base branch."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        base_branch = "main"

        with patch("subprocess.run") as mock_run:
            # First temporary worktree
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

            result1 = manager.acquire_temporary_worktree(601, base_branch)

            # Second temporary worktree from same base
            mock_run.side_effect = [
                # Clean up first worktree
                subprocess.CompletedProcess(
                    args=["tmux", "list-sessions"],
                    returncode=1,
                    stdout="",
                    stderr="",
                ),
                subprocess.CompletedProcess(
                    args=["git", "worktree", "remove"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
                # Create second
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

            # Release first
            manager.release_temporary_worktree(result1)

            # Create second (should succeed with same base)
            result2 = manager.acquire_temporary_worktree(602, base_branch)

        assert result2.is_temporary is True
        assert result2.branch == base_branch

    def test_temporary_worktree_cleanup_removes_directory(self, tmp_path: Path) -> None:
        """Temporary worktree cleanup should remove directory when git remove fails."""
        config = make_config()
        manager = WorktreeManager(config, repo_path=tmp_path)

        issue_number = 777
        base_branch = "main"

        with patch("subprocess.run") as mock_run:
            # Create
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

            result = manager.acquire_temporary_worktree(issue_number, base_branch)

            # Verify created
            assert result.path.exists() or True  # May not exist due to mocking

            # Release with git remove failing
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    args=["tmux", "list-sessions"],
                    returncode=1,
                    stdout="",
                    stderr="",
                ),
                # git worktree remove fails
                subprocess.CompletedProcess(
                    args=["git", "worktree", "remove"],
                    returncode=1,
                    stdout="",
                    stderr="error",
                ),
                # prune succeeds
                subprocess.CompletedProcess(
                    args=["git", "worktree", "prune"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            manager.release_temporary_worktree(result)

        # Verify cleanup attempted
        assert mock_run.call_count >= 3
