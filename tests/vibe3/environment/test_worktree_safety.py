"""Tests for worktree cleanup safety checks."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from vibe3.environment.worktree_support import recycle_worktree_path


class TestWorktreeManagerSafety:
    """Tests for worktree cleanup safety checks."""

    def test_recycle_skips_when_active_tmux_session_found(self, tmp_path: Path) -> None:
        """Skip cleanup if tmux session is using worktree."""
        worktree_path = tmp_path / ".worktrees" / "issue-123"
        worktree_path.mkdir(parents=True)

        # Mock tmux list-sessions to return an active session
        with patch("subprocess.run") as mock_run:
            # First call: tmux list-sessions
            # Second call: git worktree remove (should not be called)
            mock_run.side_effect = [
                subprocess.CompletedProcess(
                    args=["tmux", "list-sessions"],
                    returncode=0,
                    stdout=f"vibe3-manager-123:{worktree_path}",
                    stderr="",
                ),
            ]

            recycle_worktree_path(tmp_path, worktree_path)

        # Verify tmux check was called
        assert mock_run.call_count == 1
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "tmux"
        assert call_args[1] == "list-sessions"

        # Verify worktree still exists
        assert worktree_path.exists()

    def test_recycle_proceeds_when_no_tmux_sessions(self, tmp_path: Path) -> None:
        """recycle_worktree_path should proceed with cleanup when no tmux sessions."""
        worktree_path = tmp_path / ".worktrees" / "issue-456"
        worktree_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # tmux list-sessions: no sessions
                subprocess.CompletedProcess(
                    args=["tmux", "list-sessions"],
                    returncode=1,  # tmux returns 1 when no sessions
                    stdout="",
                    stderr="no sessions",
                ),
                # git worktree remove
                subprocess.CompletedProcess(
                    args=["git", "worktree", "remove"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            recycle_worktree_path(tmp_path, worktree_path)

        # Verify cleanup proceeded
        assert mock_run.call_count == 2
        git_remove_call = mock_run.call_args_list[1][0][0]
        assert git_remove_call[:3] == ["git", "worktree", "remove"]

    def test_recycle_proceeds_when_tmux_not_installed(self, tmp_path: Path) -> None:
        """recycle_worktree_path should proceed with cleanup when tmux not installed."""
        worktree_path = tmp_path / ".worktrees" / "issue-789"
        worktree_path.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            # tmux command not found
            mock_run.side_effect = [
                FileNotFoundError("tmux not found"),
                # git worktree remove proceeds anyway
                subprocess.CompletedProcess(
                    args=["git", "worktree", "remove"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            recycle_worktree_path(tmp_path, worktree_path)

        # Verify cleanup proceeded despite tmux not being available
        assert mock_run.call_count == 2

    def test_recycle_skips_for_nested_worktree_path(self, tmp_path: Path) -> None:
        """Skip if session path starts with worktree path."""
        worktree_path = tmp_path / ".worktrees" / "issue-999"
        worktree_path.mkdir(parents=True)

        # Session path is nested under worktree
        session_path = worktree_path / "src" / "project"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["tmux", "list-sessions"],
                returncode=0,
                stdout=f"vibe3-manager-999:{session_path}",
                stderr="",
            )

            recycle_worktree_path(tmp_path, worktree_path)

        # Verify cleanup was skipped
        assert worktree_path.exists()
        assert mock_run.call_count == 1  # Only tmux check, no git commands
