"""Git client - 封装 git 命令，提供统一改动获取接口."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from vibe3.clients.git_branch_ops import (
    branch_exists as _branch_exists,
)
from vibe3.clients.git_branch_ops import (
    check_merge_conflicts as _check_merge_conflicts,
)
from vibe3.clients.git_branch_ops import (
    create_branch as _create_branch,
)
from vibe3.clients.git_branch_ops import (
    create_branch_ref as _create_branch_ref,
)
from vibe3.clients.git_branch_ops import (
    delete_branch as _delete_branch,
)
from vibe3.clients.git_branch_ops import (
    delete_remote_branch as _delete_remote_branch,
)
from vibe3.clients.git_branch_ops import (
    get_merge_base as _get_merge_base,
)
from vibe3.clients.git_branch_ops import (
    switch_branch as _switch_branch,
)
from vibe3.clients.git_status_ops import (
    get_changed_files as _get_changed_files,
)
from vibe3.clients.git_status_ops import (
    get_diff as _get_diff,
)
from vibe3.clients.git_status_ops import (
    get_untracked_files as _get_untracked_files,
)
from vibe3.clients.git_status_ops import (
    has_uncommitted_changes as _has_uncommitted_changes,
)
from vibe3.clients.git_status_ops import (
    stash_apply as _stash_apply,
)
from vibe3.clients.git_status_ops import (
    stash_push as _stash_push,
)
from vibe3.clients.git_worktree_ops import (
    _parse_worktree_list,
)
from vibe3.clients.git_worktree_ops import (
    find_worktree_path_for_branch as _find_worktree_path_for_branch,
)
from vibe3.clients.git_worktree_ops import (
    get_current_branch as _get_current_branch,
)
from vibe3.clients.git_worktree_ops import (
    get_current_commit as _get_current_commit,
)
from vibe3.clients.git_worktree_ops import (
    get_git_common_dir as _get_git_common_dir,
)
from vibe3.clients.git_worktree_ops import (
    get_safe_main_branch_name as _get_safe_main_branch_name,
)
from vibe3.clients.git_worktree_ops import (
    get_worktree_root as _get_worktree_root,
)
from vibe3.clients.git_worktree_ops import (
    get_worktrees_for_branch as _get_worktrees_for_branch,
)
from vibe3.clients.git_worktree_ops import (
    is_branch_occupied_by_worktree as _is_branch_occupied_by_worktree,
)
from vibe3.exceptions import GitError
from vibe3.models.change_source import ChangeSource

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


class GitClientProtocol(Protocol):
    """Git client 协议定义."""

    def get_current_branch(self) -> str: ...

    def get_commit_subjects(
        self, base_ref: str, head_ref: str = "HEAD"
    ) -> list[str]: ...

    def get_changed_files(self, source: ChangeSource) -> list[str]: ...

    def get_diff(self, source: ChangeSource) -> str: ...


class GitClient:
    """Git client，封装 git 命令操作."""

    def __init__(self, github_client: "GitHubClient | None" = None) -> None:
        """初始化 GitClient.

        Args:
            github_client: 可选的 GitHubClient 实例，用于处理 PR 相关操作
        """
        self._github_client = github_client
        self._pr_diff_cache: dict[int, str] = {}

    def _run(self, args: list[str]) -> str:
        """执行 git 命令，统一错误处理.

        Args:
            args: git 子命令及参数列表

        Returns:
            命令标准输出

        Raises:
            GitError: git 命令执行失败
        """
        cmd = ["git", *args]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitError(" ".join(args), e.stderr.strip()) from e

    def get_current_branch(self) -> str:
        """获取当前分支名."""
        return _get_current_branch(self._run)

    def get_commit_subjects(self, base_ref: str, head_ref: str = "HEAD") -> list[str]:
        """Get commit subjects between base and head refs."""
        output = self._run(
            ["log", f"{base_ref}..{head_ref}", "--oneline", "--format=%s"]
        )
        return [line.strip() for line in output.splitlines() if line.strip()]

    def get_current_commit(self) -> str:
        """Get current HEAD commit SHA."""
        return _get_current_commit(self._run)

    def get_git_common_dir(self) -> str:
        """Get the shared .git directory path (for worktrees)."""
        return _get_git_common_dir(self._run)

    def get_worktree_root(self) -> str:
        """Get the top-level path of the current worktree."""
        return _get_worktree_root(self._run)

    def get_safe_main_branch_name(self) -> str:
        """Get the worktree-specific safe branch name."""
        return _get_safe_main_branch_name(self._run)

    def is_branch_occupied_by_worktree(self, branch_name: str) -> bool:
        """Check whether any worktree already has this branch checked out."""
        return _is_branch_occupied_by_worktree(self._run, branch_name)

    def find_worktree_path_for_branch(self, branch_name: str) -> Path | None:
        """Find worktree path whose checked-out branch matches ``branch_name``."""
        return _find_worktree_path_for_branch(self._run, branch_name)

    def get_worktrees_for_branch(self, branch_name: str) -> list[str]:
        """Return paths of worktrees that have the given branch checked out."""
        return _get_worktrees_for_branch(self._run, branch_name)

    def list_worktrees(self) -> list[tuple[str, str]]:
        """List all worktrees.

        Returns:
            List of (worktree_path, branch_ref) tuples.
        """
        output = self._run(["worktree", "list", "--porcelain"])
        return _parse_worktree_list(output)

    def get_changed_files(self, source: ChangeSource) -> list[str]:
        """统一接口：获取改动文件列表."""
        return _get_changed_files(self._run, source, self._github_client)

    def get_diff(self, source: ChangeSource) -> str:
        """统一接口：获取 diff 内容."""
        return _get_diff(self._run, source, self._github_client, self._pr_diff_cache)

    def get_untracked_files(self) -> list[str]:
        """Return untracked files in the worktree."""
        return _get_untracked_files(self._run)

    def stash_push(self, message: str | None = None) -> str:
        """Stash current changes, return stash ref."""
        return _stash_push(self._run, message)

    def stash_apply(self, stash_ref: str) -> None:
        """Apply and drop stash."""
        return _stash_apply(self._run, stash_ref)

    def has_uncommitted_changes(self) -> bool:
        """Check if working directory is dirty."""
        return _has_uncommitted_changes(self._run)

    # ── 分支管理方法（委托给 git_branch_ops）──────────────────

    def create_branch(self, branch_name: str, start_ref: str = "origin/main") -> None:
        """Create a new branch from start_ref and switch to it."""
        _create_branch(branch_name, start_ref)

    def create_branch_ref(
        self, branch_name: str, start_ref: str = "origin/main"
    ) -> None:
        """Create a branch ref without checking it out."""
        _create_branch_ref(branch_name, start_ref)

    def switch_branch(self, branch_name: str) -> None:
        """Switch to existing branch."""
        _switch_branch(branch_name)

    def delete_branch(
        self,
        branch_name: str,
        force: bool = False,
        skip_if_worktree: bool = False,
    ) -> None:
        """Delete local branch."""
        _delete_branch(branch_name, force=force, skip_if_worktree=skip_if_worktree)

    def delete_remote_branch(self, branch_name: str) -> None:
        """Delete remote branch."""
        _delete_remote_branch(branch_name)

    def get_merge_base(self, branch1: str, branch2: str) -> str:
        """Get merge-base commit between two branches."""
        return _get_merge_base(branch1, branch2)

    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists (local or remote)."""
        return _branch_exists(branch_name)

    def push_branch(
        self,
        branch_name: str,
        remote: str = "origin",
        set_upstream: bool = True,
    ) -> None:
        """Push branch to remote.

        Args:
            branch_name: Branch to push
            remote: Remote name, default origin
            set_upstream: Whether to set upstream tracking
        """
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.extend([remote, branch_name])
        self._run(args)

    def fetch(self, remote: str = "origin", ref: str | None = None) -> None:
        """Fetch from remote.

        Args:
            remote: Remote name
            ref: Optional refspec (e.g. 'main'). Fetches all if None.
        """
        args = ["fetch", remote]
        if ref:
            args.append(ref)
        self._run(args)

    def check_merge_conflicts(self, target_ref: str = "origin/main") -> bool:
        """Dry-run merge to detect conflicts without modifying working tree."""
        return _check_merge_conflicts(self._run, target_ref)
