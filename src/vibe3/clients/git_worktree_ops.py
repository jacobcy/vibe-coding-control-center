"""Git worktree operations - 封装 worktree 和分支相关 git 命令."""

import hashlib
import re
from pathlib import Path
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


def get_worktree_root(run: Callable[[list[str]], str]) -> str:
    """Get the top-level path of the current worktree."""
    worktree_root = run(["rev-parse", "--show-toplevel"])
    logger.bind(
        domain="git",
        action="get_worktree_root",
        worktree_root=worktree_root,
    ).debug("Got worktree root")
    return worktree_root


def get_safe_main_branch_name(run: Callable[[list[str]], str]) -> str:
    """Build the worktree-specific safe branch name used after flow close."""
    worktree_root = get_worktree_root(run)
    worktree_name = Path(worktree_root).name
    safe_name = worktree_name.lower()
    safe_name = re.sub(r"[^a-z0-9._-]", "-", safe_name)
    safe_name = safe_name.strip("-./")
    while "--" in safe_name:
        safe_name = safe_name.replace("--", "-")
    suffix = safe_name or "default"
    root_hash = hashlib.sha1(worktree_root.encode("utf-8")).hexdigest()[:8]
    branch_name = f"vibe/main-safe/{suffix}-{root_hash}"
    logger.bind(
        domain="git",
        action="get_safe_main_branch_name",
        branch=branch_name,
    ).debug("Got safe main branch name")
    return branch_name


def is_branch_occupied_by_worktree(
    run: Callable[[list[str]], str],
    branch_name: str,
) -> bool:
    """Check whether any worktree has the branch checked out."""
    if not branch_name:
        return False

    current_worktree = get_worktree_root(run)
    current_branch = run(["branch", "--show-current"])
    output = run(["worktree", "list", "--porcelain"])

    occupied = False
    record_worktree = ""
    record_branch = ""

    def flush_record() -> None:
        nonlocal occupied, record_worktree, record_branch
        if record_branch != f"refs/heads/{branch_name}":
            record_worktree = ""
            record_branch = ""
            return

        if branch_name == current_branch:
            if record_worktree and record_worktree != current_worktree:
                occupied = True
        elif record_worktree:
            occupied = True

        record_worktree = ""
        record_branch = ""

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            flush_record()
            continue
        if line.startswith("worktree "):
            record_worktree = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            record_branch = line.split(" ", 1)[1]

    flush_record()
    logger.bind(
        domain="git",
        action="is_branch_occupied_by_worktree",
        branch=branch_name,
        occupied=occupied,
    ).debug("Checked branch worktree occupation")
    return occupied
