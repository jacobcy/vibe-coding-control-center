"""Git worktree operations - 封装 worktree 和分支相关 git 命令."""

from typing import Callable

from loguru import logger


def get_current_branch(run: Callable[[list[str]], str]) -> str:
    """获取当前分支名.

    Args:
        run: Git command runner function

    Returns:
        当前分支名
    """
    branch = run(["rev-parse", "--abbrev-ref", "HEAD"])
    logger.bind(domain="git", action="get_current_branch", branch=branch).debug(
        "Got current branch"
    )
    return branch


def get_current_commit(run: Callable[[list[str]], str]) -> str:
    """Get current HEAD commit SHA.

    Args:
        run: Git command runner function

    Returns:
        Full commit SHA of current HEAD
    """
    commit = run(["rev-parse", "HEAD"])
    logger.bind(domain="git", action="get_current_commit", commit=commit[:7]).debug(
        "Got current commit"
    )
    return commit


def get_git_common_dir(run: Callable[[list[str]], str]) -> str:
    """Get the shared .git directory path (for worktrees).

    In linked worktrees, this returns the common git directory
    instead of the worktree-local .git/worktrees/<name> path.

    Args:
        run: Git command runner function

    Returns:
        Absolute path to the shared .git directory

    Raises:
        GitError: git command execution failed
    """
    git_common_dir = run(["rev-parse", "--git-common-dir"])
    logger.bind(
        domain="git", action="get_git_common_dir", git_common_dir=git_common_dir
    ).debug("Got git common directory")
    return git_common_dir
