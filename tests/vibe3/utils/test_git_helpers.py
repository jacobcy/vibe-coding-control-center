"""Tests for git helper utilities — bare repo detection and repo root resolution."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.utils.git_helpers import (
    RepositoryLayoutError,
    find_repo_root,
    get_git_common_dir,
    resolve_repo_root_from_common_dir,
)


def _run_git(args: list[str], cwd: Path) -> str:
    """Run Git without inheriting repository-selection environment variables."""
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_PREFIX", "GIT_COMMON_DIR"):
        env.pop(key, None)
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _create_non_bare_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Create a non-bare main checkout with a linked worktree below it."""
    main = tmp_path / "main"
    main.mkdir()
    _run_git(["init", "-b", "main"], main)
    _run_git(["config", "user.email", "test@example.com"], main)
    _run_git(["config", "user.name", "Test"], main)
    _run_git(["-c", "core.hooksPath=", "commit", "--allow-empty", "-m", "init"], main)
    worktree = main / ".worktrees" / "topic"
    _run_git(["worktree", "add", "-b", "topic", str(worktree)], main)
    return main, worktree


def test_real_non_bare_main_worktree_returns_main_checkout(tmp_path: Path) -> None:
    """main/.worktrees uses the checked-out main directory as management root."""
    main, worktree = _create_non_bare_worktree(tmp_path)
    common = _run_git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree
    )

    assert resolve_repo_root_from_common_dir(common) == main


def test_real_bare_repo_worktree_returns_bare_repo(tmp_path: Path) -> None:
    """bare_repo/.worktrees uses the bare repository as management root."""
    seed, _ = _create_non_bare_worktree(tmp_path)
    bare_repo = tmp_path / "bare_repo"
    _run_git(["clone", "--bare", str(seed), str(bare_repo)], tmp_path)
    worktree = bare_repo / ".worktrees" / "topic"
    _run_git(
        ["worktree", "add", "-b", "bare-topic", str(worktree), "main"],
        bare_repo,
    )
    common = _run_git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree
    )

    assert resolve_repo_root_from_common_dir(common) == bare_repo


def test_non_bare_with_core_bare_true_returns_parent_checkout(
    tmp_path: Path,
) -> None:
    """When core.bare=true is set in a non-bare repo with linked worktrees,
    resolve_repo_root_from_common_dir must still return the parent checkout
    (the real management root), not the .git directory."""
    main, worktree = _create_non_bare_worktree(tmp_path)
    # Simulate worktree topology: set core.bare=true in the main .git/config
    _run_git(["config", "core.bare", "true"], main)
    common = _run_git(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree
    )
    # common is main/.git, and even with core.bare=true it has linked
    # worktrees — the management root must be the parent checkout.
    assert resolve_repo_root_from_common_dir(common) == main


def test_non_core_bare_key_does_not_mark_repo_bare(tmp_path: Path) -> None:
    """Only core.bare controls repository topology classification."""
    main, _ = _create_non_bare_worktree(tmp_path)
    _run_git(["config", "other.bare", "true"], main)

    assert resolve_repo_root_from_common_dir(main / ".git") == main


def test_ambiguous_common_dir_raises_actionable_layout_error(tmp_path: Path) -> None:
    """An unclassified non-.git common directory must fail with path context."""
    ambiguous = tmp_path / "ambiguous"
    ambiguous.mkdir()
    (ambiguous / "config").write_text("[core]\n", encoding="utf-8")

    with pytest.raises(RepositoryLayoutError) as exc_info:
        resolve_repo_root_from_common_dir(ambiguous)

    message = str(exc_info.value)
    assert f"cwd={Path.cwd()}" in message
    assert f"git_common_dir={ambiguous}" in message
    assert "core.bare is not set" in message


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

    def test_commented_bare_without_core_value_reports_ambiguous_layout(
        self, tmp_path: Path
    ) -> None:
        """A comment is not topology evidence, so an unusual root is ambiguous."""
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
            with pytest.raises(RepositoryLayoutError, match="core.bare is not set"):
                find_repo_root()

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
