"""Git client - 封装 git 命令，提供统一改动获取接口."""

import re
import subprocess
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from vibe3.clients.git_diff_utils import extract_file_diff
from vibe3.exceptions import GitError
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

    def get_current_branch(self) -> str:
        ...

    def get_worktree_name(self) -> str:
        ...

    def get_changed_files(self, source: ChangeSource) -> list[str]:
        ...

    def get_diff(self, source: ChangeSource) -> str:
        ...


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
            assert isinstance(source, CommitSource)
            files = self._get_commit_files(source.sha)
        elif source.type == ChangeSourceType.BRANCH:
            assert isinstance(source, BranchSource)
            files = self._get_branch_files(source.branch, source.base)
        elif source.type == ChangeSourceType.PR:
            assert isinstance(source, PRSource)
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
            assert isinstance(source, CommitSource)
            diff = self._run(["show", source.sha, "--stat"])
        elif source.type == ChangeSourceType.BRANCH:
            assert isinstance(source, BranchSource)
            diff = self._run(["diff", f"{source.base}...{source.branch}"])
        elif source.type == ChangeSourceType.PR:
            assert isinstance(source, PRSource)
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

    def get_diff_hunk_ranges(
        self, file_path: str, source: ChangeSource
    ) -> list[tuple[int, int]]:
        """Get changed line ranges from git diff for a specific file.

        Simple heuristic: parse diff hunks to find changed line numbers.
        Useful for finding which functions were changed.

        Args:
            file_path: Relative file path
            source: Change source (commit/branch/pr)

        Returns:
            List of (start_line, end_line) tuples for changed hunks

        Example:
            >>> client = GitClient()
            >>> source = CommitSource(sha="abc123")
            >>> ranges = client.get_diff_hunk_ranges("src/foo.py", source)
            >>> # [(10, 15), (42, 50)]
        """
        log = logger.bind(
            domain="git",
            action="get_diff_hunk_ranges",
            file=file_path,
            source_type=source.type,
        )
        log.debug("Getting diff hunk ranges")

        try:
            # Get diff for this specific file
            if source.type == ChangeSourceType.COMMIT:
                assert isinstance(source, CommitSource)
                diff = self._run(
                    ["diff", f"{source.sha}^", source.sha, "--", file_path]
                )
            elif source.type == ChangeSourceType.BRANCH:
                assert isinstance(source, BranchSource)
                diff = self._run(
                    ["diff", f"{source.base}...{source.branch}", "--", file_path]
                )
            elif source.type == ChangeSourceType.PR:
                assert isinstance(source, PRSource)
                # Use GitHub API to get the full PR diff, then extract this file
                if not self._github_client:
                    raise GitError(
                        "get_diff_hunk_ranges",
                        "PR source requires GitHubClient injection",
                    )
                full_diff = self._get_pr_diff_cached(source.pr_number)
                diff = extract_file_diff(full_diff, file_path)
            else:
                # Uncommitted changes
                diff = self._run(["diff", "HEAD", "--", file_path])

            if not diff:
                return []

            # Parse diff hunks: @@ -old_start,old_count +new_start,new_count @@
            hunk_pattern = re.compile(
                r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE
            )
            ranges: list[tuple[int, int]] = []

            for match in hunk_pattern.finditer(diff):
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1
                end = start + count - 1
                ranges.append((start, end))

            log.bind(hunk_count=len(ranges)).debug("Got diff hunk ranges")
            return ranges

        except GitError:
            # If git command fails, return empty (graceful degradation)
            log.warning("Failed to get diff hunks, returning empty")
            return []

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
