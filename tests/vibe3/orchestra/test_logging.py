"""Test orchestra logging functions."""

from pathlib import Path
from unittest.mock import patch

import vibe3.orchestra.logging as logging_mod
from vibe3.orchestra.logging import _repo_root, orchestra_events_log_path


class TestRepoRootResolution:
    """Test that _repo_root correctly resolves main repository root."""

    def test_repo_root_returns_absolute_path(self):
        """_repo_root should always return an absolute path."""
        root = _repo_root()
        assert root.is_absolute()

    def test_repo_root_contains_git_dir(self):
        """_repo_root should contain a .git directory."""
        root = _repo_root()
        git_dir = root / ".git"
        assert git_dir.exists()

    def test_repo_root_uses_git_common_dir_in_worktree(self):
        """_repo_root should use git common dir to resolve main repo root."""
        # This test verifies the fix for the issue where _repo_root
        # would return the worktree root instead of the main repo root
        root = _repo_root()

        # In a worktree, the root should NOT contain .worktrees
        # It should be the main repository root
        assert ".worktrees" not in str(root)

    def test_repo_root_fallback_on_git_failure(self):
        """_repo_root should fallback to path-based detection if git fails."""
        # Clear the lru_cache so the mocked subprocess is actually called
        logging_mod._repo_root.cache_clear()
        try:
            with patch("subprocess.run") as mock_run:
                # Simulate git command failure
                mock_run.side_effect = FileNotFoundError("git not found")

                root = _repo_root()

                # Should still return a Path object
                assert isinstance(root, Path)
                # Should be an absolute path
                assert root.is_absolute()
        finally:
            # Restore the cache so subsequent tests use the real git result
            logging_mod._repo_root.cache_clear()

    def test_orchestra_events_log_path_returns_main_repo_path(self):
        """orchestra_events_log_path should return path in main repository."""
        log_path = orchestra_events_log_path()

        # Should be an absolute path
        assert log_path.is_absolute()

        # Should not contain .worktrees (should be main repo path)
        assert ".worktrees" not in str(log_path)

        # Should end with temp/logs/orchestra/events.log
        assert str(log_path).endswith("temp/logs/orchestra/events.log")

        # Parent directory should exist (orchestra_events_log_path creates it)
        assert log_path.parent.exists()
