"""Git status operations - 封装 diff、status、stash 相关 git 命令."""

from typing import TYPE_CHECKING, Callable

from loguru import logger

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


def get_changed_files(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
) -> list[str]:
    """统一接口：获取改动文件列表.

    Args:
        run: Git command runner function
        source: 改动源（PR/Commit/Branch/Uncommitted）
        github_client: 可选的 GitHubClient 实例，用于处理 PR 相关操作

    Returns:
        改动文件路径列表

    Raises:
        GitError: git 命令执行失败
    """
    log = logger.bind(domain="git", action="get_changed_files", source_type=source.type)
    log.info("Getting changed files")

    if source.type == ChangeSourceType.UNCOMMITTED:
        files = _get_uncommitted_files(run)
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        files = _get_commit_files(run, source.sha)
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        files = _get_branch_files(run, source.branch, source.base)
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_changed_files",
                "PR source requires GitHubClient injection",
            )
        files = github_client.get_pr_files(source.pr_number)
    else:
        raise GitError("get_changed_files", f"Unknown source type: {source.type}")

    log.bind(file_count=len(files)).success("Got changed files")
    return files


def get_diff(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
    pr_diff_cache: dict[int, str] | None = None,
) -> str:
    """统一接口：获取 diff 内容.

    Args:
        run: Git command runner function
        source: 改动源（PR/Commit/Branch/Uncommitted）
        github_client: 可选的 GitHubClient 实例，用于处理 PR 相关操作
        pr_diff_cache: 可选的 PR diff 缓存字典

    Returns:
        diff 文本

    Raises:
        GitError: git 命令执行失败
    """
    log = logger.bind(domain="git", action="get_diff", source_type=source.type)
    log.info("Getting diff")

    if source.type == ChangeSourceType.UNCOMMITTED:
        diff = run(["diff", "HEAD"])
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        diff = run(["show", source.sha, "--stat"])
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        diff = run(["diff", f"{source.base}...{source.branch}"])
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_diff",
                "PR source requires GitHubClient injection",
            )
        if pr_diff_cache is not None and source.pr_number in pr_diff_cache:
            diff = pr_diff_cache[source.pr_number]
        else:
            diff = github_client.get_pr_diff(source.pr_number)
            if pr_diff_cache is not None:
                pr_diff_cache[source.pr_number] = diff
    else:
        raise GitError("get_diff", f"Unknown source type: {source.type}")

    log.bind(diff_len=len(diff)).success("Got diff")
    return diff


def _get_uncommitted_files(run: Callable[[list[str]], str]) -> list[str]:
    """获取未提交改动文件（暂存 + 工作区）."""
    staged = run(["diff", "--name-only", "--cached"])
    unstaged = run(["diff", "--name-only"])
    untracked = run(["ls-files", "--others", "--exclude-standard"])
    all_files = set()
    for line in (staged + "\n" + unstaged + "\n" + untracked).splitlines():
        if line.strip():
            all_files.add(line.strip())
    return sorted(all_files)


def get_untracked_files(run: Callable[[list[str]], str]) -> list[str]:
    """获取未跟踪文件列表."""
    output = run(["ls-files", "--others", "--exclude-standard"])
    return [f for f in output.splitlines() if f.strip()]


def _get_commit_files(run: Callable[[list[str]], str], sha: str) -> list[str]:
    """获取指定 commit 的改动文件."""
    output = run(["diff-tree", "--no-commit-id", "-r", "--name-only", "-m", sha])
    return sorted(set(f for f in output.splitlines() if f.strip()))


def _get_branch_files(
    run: Callable[[list[str]], str], branch: str, base: str
) -> list[str]:
    """获取分支相对于 base 的改动文件."""
    output = run(["diff", "--name-only", f"{base}...{branch}"])
    return [f for f in output.splitlines() if f.strip()]


def stash_push(run: Callable[[list[str]], str], message: str | None = None) -> str:
    """Stash current changes, return stash ref.

    Args:
        run: Git command runner function
        message: Optional stash message

    Returns:
        Stash reference (e.g., stash@{0})
    """
    args = ["stash", "push"]
    if message:
        args.extend(["-m", message])
    run(args)
    stash_ref = "stash@{0}"
    logger.bind(
        domain="git", action="stash_push", stash_ref=stash_ref, message=message
    ).info("Stashed changes")
    return stash_ref


def stash_apply(run: Callable[[list[str]], str], stash_ref: str) -> None:
    """Apply and drop stash.

    Args:
        run: Git command runner function
        stash_ref: Stash reference to apply
    """
    run(["stash", "pop", stash_ref])
    logger.bind(domain="git", action="stash_apply", stash_ref=stash_ref).info(
        "Applied stash"
    )


def has_uncommitted_changes(run: Callable[[list[str]], str]) -> bool:
    """Check if working directory is dirty.

    Args:
        run: Git command runner function

    Returns:
        True if there are uncommitted changes
    """
    try:
        status = run(["status", "--porcelain"])
        return bool(status)
    except GitError:
        return False
