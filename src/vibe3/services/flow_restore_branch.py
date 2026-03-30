"""Helpers for selecting post-close restore branches."""

from pathlib import Path

_BASELINE_WORKTREE_BRANCHES: dict[str, str] = {
    "main": "main",
    "develop": "develop",
    "bugfix": "bugfix",
}


def resolve_baseline_branch_for_worktree_root(worktree_root: str | None) -> str | None:
    """Resolve baseline restore branch for a worktree root path."""
    if not worktree_root:
        return None
    worktree_name = Path(worktree_root).name.lower()
    return _BASELINE_WORKTREE_BRANCHES.get(worktree_name)


def is_baseline_restore_branch(branch: str) -> bool:
    """Return whether branch is one of baseline restore branches."""
    return branch in _BASELINE_WORKTREE_BRANCHES
