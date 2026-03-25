"""Git client - 封装 git 命令，提供统一改动获取接口."""

import subprocess
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from vibe3.clients.git_branch_ops import (
    branch_exists as _branch_exists,
)
from vibe3.clients.git_branch_ops import (
    create_branch as _create_branch,
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
from vibe3.exceptions import GitError, SystemError
from vibe3.models.change_source import (
    BranchSource,
    ChangeSource,
    ChangeSourceType,
    CommitSource,
    PRSource,
)

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


class GitClientProtocol(Protocol):
    """Git client 协议定义."""

    def get_current_branch(self) -> str: ...

    def get_worktree_name(self) -> str: ...

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
        """获取当前分支名.

        Returns:
            当前分支名
        """
        branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        logger.bind(domain="git", action="get_current_branch", branch=branch).debug(
            "Got current branch"
        )
        return branch

    def get_current_commit(self) -> str:
        """Get current HEAD commit SHA.

        Returns:
            Full commit SHA of current HEAD
        """
        commit = self._run(["rev-parse", "HEAD"])
        logger.bind(domain="git", action="get_current_commit", commit=commit[:7]).debug(
            "Got current commit"
        )
        return commit

    def get_worktree_name(self) -> str:
        """获取当前 worktree 名称（路径最后一段）.

        Returns:
            Worktree 名称
        """
        root = self._run(["rev-parse", "--show-toplevel"])
        name = root.split("/")[-1]
        logger.bind(domain="git", action="get_worktree_name", name=name).debug(
            "Got worktree name"
        )
        return name

    def get_git_dir(self) -> str:
        """Get the .git directory path.

        Returns:
            Absolute path to the .git directory

        Raises:
            GitError: git command execution failed
        """
        git_dir = self._run(["rev-parse", "--git-dir"])
        logger.bind(domain="git", action="get_git_dir", git_dir=git_dir).debug(
            "Got git directory"
        )
        return git_dir

    def get_git_common_dir(self) -> str:
        """Get the shared .git directory path (for worktrees).

        In linked worktrees, this returns the common git directory
        instead of the worktree-local .git/worktrees/<name> path.

        Returns:
            Absolute path to the shared .git directory

        Raises:
            GitError: git command execution failed
        """
        git_common_dir = self._run(["rev-parse", "--git-common-dir"])
        logger.bind(
            domain="git", action="get_git_common_dir", git_common_dir=git_common_dir
        ).debug("Got git common directory")
        return git_common_dir

    def get_changed_files(self, source: ChangeSource) -> list[str]:
        """统一接口：获取改动文件列表.

        Args:
            source: 改动源（PR/Commit/Branch/Uncommitted）

        Returns:
            改动文件路径列表

        Raises:
            GitError: git 命令执行失败
        """
        log = logger.bind(
            domain="git", action="get_changed_files", source_type=source.type
        )
        log.info("Getting changed files")

        if source.type == ChangeSourceType.UNCOMMITTED:
            files = self._get_uncommitted_files()
        elif source.type == ChangeSourceType.COMMIT:
            if not isinstance(source, CommitSource):
                raise SystemError(
                    f"Type mismatch: expected CommitSource, got {type(source).__name__}"
                )
            files = self._get_commit_files(source.sha)
        elif source.type == ChangeSourceType.BRANCH:
            if not isinstance(source, BranchSource):
                raise SystemError(
                    f"Type mismatch: expected BranchSource, got {type(source).__name__}"
                )
            files = self._get_branch_files(source.branch, source.base)
        elif source.type == ChangeSourceType.PR:
            if not isinstance(source, PRSource):
                raise SystemError(
                    f"Type mismatch: expected PRSource, got {type(source).__name__}"
                )
            if not self._github_client:
                raise GitError(
                    "get_changed_files",
                    "PR source requires GitHubClient injection",
                )
            files = self._github_client.get_pr_files(source.pr_number)
        else:
            raise GitError("get_changed_files", f"Unknown source type: {source.type}")

        log.bind(file_count=len(files)).success("Got changed files")
        return files

    def get_diff(self, source: ChangeSource) -> str:
        """统一接口：获取 diff 内容.

        Args:
            source: 改动源（PR/Commit/Branch/Uncommitted）

        Returns:
            diff 文本

        Raises:
            GitError: git 命令执行失败
        """
        log = logger.bind(domain="git", action="get_diff", source_type=source.type)
        log.info("Getting diff")

        if source.type == ChangeSourceType.UNCOMMITTED:
            diff = self._run(["diff", "HEAD"])
        elif source.type == ChangeSourceType.COMMIT:
            if not isinstance(source, CommitSource):
                raise SystemError(
                    f"Type mismatch: expected CommitSource, got {type(source).__name__}"
                )
            diff = self._run(["show", source.sha, "--stat"])
        elif source.type == ChangeSourceType.BRANCH:
            if not isinstance(source, BranchSource):
                raise SystemError(
                    f"Type mismatch: expected BranchSource, got {type(source).__name__}"
                )
            diff = self._run(["diff", f"{source.base}...{source.branch}"])
        elif source.type == ChangeSourceType.PR:
            if not isinstance(source, PRSource):
                raise SystemError(
                    f"Type mismatch: expected PRSource, got {type(source).__name__}"
                )
            if not self._github_client:
                raise GitError(
                    "get_diff",
                    "PR source requires GitHubClient injection",
                )
            diff = self._github_client.get_pr_diff(source.pr_number)
        else:
            raise GitError("get_diff", f"Unknown source type: {source.type}")

        log.bind(diff_len=len(diff)).success("Got diff")
        return diff

    # ── 私有方法 ──────────────────────────────────────────────

    def _get_uncommitted_files(self) -> list[str]:
        """获取未提交改动文件（暂存 + 工作区）."""
        staged = self._run(["diff", "--name-only", "--cached"])
        unstaged = self._run(["diff", "--name-only"])
        all_files = set()
        for line in (staged + "\n" + unstaged).splitlines():
            if line.strip():
                all_files.add(line.strip())
        return sorted(all_files)

    def _get_commit_files(self, sha: str) -> list[str]:
        """获取指定 commit 的改动文件."""
        output = self._run(["diff-tree", "--no-commit-id", "-r", "--name-only", sha])
        return [f for f in output.splitlines() if f.strip()]

    def _get_branch_files(self, branch: str, base: str) -> list[str]:
        """获取分支相对于 base 的改动文件."""
        output = self._run(["diff", "--name-only", f"{base}...{branch}"])
        return [f for f in output.splitlines() if f.strip()]

    def _get_pr_diff_cached(self, pr_number: int) -> str:
        """Get PR diff with caching.

        Args:
            pr_number: PR number

        Returns:
            Full PR diff content
        """
        if pr_number not in self._pr_diff_cache:
            if not self._github_client:
                raise GitError(
                    "get_pr_diff_cached",
                    "PR source requires GitHubClient injection",
                )
            self._pr_diff_cache[pr_number] = self._github_client.get_pr_diff(pr_number)
        return self._pr_diff_cache[pr_number]

    # ── 分支管理方法（委托给 git_branch_ops）──────────────────

    def create_branch(self, branch_name: str, start_ref: str = "origin/main") -> None:
        """Create a new branch from start_ref.

        Args:
            branch_name: Name of the new branch
            start_ref: Starting reference (default: origin/main)
        """
        _create_branch(branch_name, start_ref)

    def switch_branch(self, branch_name: str) -> None:
        """Switch to existing branch.

        Args:
            branch_name: Branch to switch to
        """
        _switch_branch(branch_name)

    def delete_branch(self, branch_name: str, force: bool = False) -> None:
        """Delete local branch.

        Args:
            branch_name: Branch to delete
            force: Force delete even if not merged
        """
        _delete_branch(branch_name, force=force)

    def delete_remote_branch(self, branch_name: str) -> None:
        """Delete remote branch.

        Args:
            branch_name: Remote branch to delete
        """
        _delete_remote_branch(branch_name)

    def get_merge_base(self, branch1: str, branch2: str) -> str:
        """Get merge-base commit between two branches.

        Args:
            branch1: First branch name
            branch2: Second branch name

        Returns:
            Commit SHA of merge-base
        """
        return _get_merge_base(branch1, branch2)

    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists (local or remote).

        Args:
            branch_name: Branch name to check

        Returns:
            True if branch exists
        """
        return _branch_exists(branch_name)

    # ── Stash 操作 ────────────────────────────────────────────

    def stash_push(self, message: str | None = None) -> str:
        """Stash current changes, return stash ref.

        Args:
            message: Optional stash message

        Returns:
            Stash reference (e.g., stash@{0})
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        self._run(args)
        stash_ref = "stash@{0}"
        logger.bind(
            domain="git", action="stash_push", stash_ref=stash_ref, message=message
        ).info("Stashed changes")
        return stash_ref

    def stash_apply(self, stash_ref: str) -> None:
        """Apply and drop stash.

        Args:
            stash_ref: Stash reference to apply
        """
        self._run(["stash", "pop", stash_ref])
        logger.bind(domain="git", action="stash_apply", stash_ref=stash_ref).info(
            "Applied stash"
        )

    def has_uncommitted_changes(self) -> bool:
        """Check if working directory is dirty.

        Returns:
            True if there are uncommitted changes
        """
        try:
            status = self._run(["status", "--porcelain"])
            return bool(status)
        except GitError:
            return False
