"""Tests for git helper utilities — bare repo detection and repo root resolution."""

from pathlib import Path
from unittest.mock import patch

from vibe3.utils.git_helpers import find_repo_root, get_git_common_dir


class TestFindRepoRootBareRepo:
    """Verify find_repo_root handles bare repositories correctly."""

    def setup_method(self):
        """Clear lru_cache before each test so patches take effect."""
        find_repo_root.cache_clear()
        get_git_common_dir.cache_clear()

    def teardown_method(self):
        """Clear caches after each test."""
        find_repo_root.cache_clear()
        get_git_common_dir.cache_clear()

    def test_bare_repo_returns_git_common_dir_directly(self, tmp_path: Path):
        """In a bare repo, git-common-dir IS the repo root."""
        bare_dir = tmp_path / "bare.git"
        bare_dir.mkdir()
        (bare_dir / "HEAD").write_text("ref: refs/heads/main\n")
        (bare_dir / "config").write_text(
            "[core]\n\trepositoryformatversion = 0\n\tbare = true\n"
        )
        (bare_dir / "objects").mkdir()
        (bare_dir / "refs").mkdir()

        with patch(
            "vibe3.utils.git_helpers.get_git_common_dir",
            return_value=str(bare_dir),
        ):
            result = find_repo_root()
            assert result == bare_dir

    def test_non_bare_repo_returns_parent_of_dot_git(self, tmp_path: Path):
        """In a non-bare repo, repo root is parent of .git directory."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        git_dir = repo_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n")
        (git_dir / "objects").mkdir()
        (git_dir / "refs").mkdir()

        with patch(
            "vibe3.utils.git_helpers.get_git_common_dir",
            return_value=str(git_dir),
        ):
            result = find_repo_root()
            assert result == repo_dir

    def test_bare_true_with_comment_not_false_positive(self, tmp_path: Path):
        """'bare = true' in a comment line should NOT trigger bare detection."""
        bare_dir = tmp_path / "not-bare.git"
        bare_dir.mkdir()
        (bare_dir / "HEAD").write_text("ref: refs/heads/main\n")
        # NOT a bare repo — bare = true is commented out
        (bare_dir / "config").write_text(
            "[core]\n\t# bare = true\n\trepositoryformatversion = 0\n"
        )
        (bare_dir / "objects").mkdir()
        (bare_dir / "refs").mkdir()

        with patch(
            "vibe3.utils.git_helpers.get_git_common_dir",
            return_value=str(bare_dir),
        ):
            result = find_repo_root()
            # Should NOT treat as bare — git config returns nothing
            assert result == bare_dir.parent

    def test_bare_config_unreadable_falls_back_to_parent(self, tmp_path: Path):
        """If config file is a directory (can't read), don't crash — fall back."""
        repo_dir = tmp_path / "weird-repo"
        repo_dir.mkdir()
        git_dir = repo_dir / ".git"
        git_dir.mkdir()
        # config is a directory, not a file — file.is_file() returns False
        (git_dir / "config").mkdir()
        (git_dir / "objects").mkdir()
        (git_dir / "refs").mkdir()

        with patch(
            "vibe3.utils.git_helpers.get_git_common_dir",
            return_value=str(git_dir),
        ):
            result = find_repo_root()
            # Should skip bare detection and return parent
            assert result == repo_dir
