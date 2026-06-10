"""Tests for rebuild postcondition checks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.services.flow.rebuild_postconditions import assert_rebuild_postconditions


class CachedGitClient:
    """Tiny fake that exposes the same worktree cache shape as GitClient."""

    def __init__(self, worktree_path: Path) -> None:
        self._worktree_list_cache = [("/tmp/old-worktree", "refs/heads/task/issue-303")]
        self.worktree_path = worktree_path

    def branch_exists(self, branch: str) -> bool:
        return branch == "task/issue-303"

    def find_worktree_path_for_branch(self, branch: str) -> Path | None:
        if self._worktree_list_cache is not None:
            return Path(self._worktree_list_cache[0][0])
        if branch == "task/issue-303":
            return self.worktree_path
        return None


def test_rebuild_postcondition_refreshes_stale_worktree_cache(
    tmp_path: Path,
) -> None:
    worktree_path = tmp_path / "repo" / ".worktrees" / "task" / "issue-303"
    worktree_path.mkdir(parents=True)
    git = CachedGitClient(worktree_path)
    store = MagicMock()
    store.get_flow_state.return_value = {"worktree_path": str(worktree_path)}

    assert_rebuild_postconditions(
        branch="task/issue-303",
        result={"worktree_path": str(worktree_path)},
        ensure_worktree=True,
        git_client=git,
        store=store,
    )

    assert git._worktree_list_cache is None
