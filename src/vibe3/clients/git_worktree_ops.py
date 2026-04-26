"""Git worktree operations - 封装 worktree 和分支相关 git 命令."""

import hashlib
import re
from pathlib import Path
from typing import Callable

from loguru import logger

from vibe3.exceptions import GitError


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
    git_common_dir = run(["rev-parse", "--path-format=absolute", "--git-common-dir"])
    if not git_common_dir:
        raise GitError("rev-parse --git-common-dir", "returned empty path")

    git_common_path = Path(git_common_dir)
    if not git_common_path.is_absolute():
        raise GitError(
            "rev-parse --git-common-dir",
            f"returned non-absolute path: {git_common_dir}",
        )

    logger.bind(
        domain="git",
        action="get_git_common_dir",
        git_common_dir=str(git_common_path),
    ).debug("Got git common directory")
    return str(git_common_path)


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


def _parse_worktree_list(output: str) -> list[tuple[str, str]]:
    """Parse ``git worktree list --porcelain`` output.

    Returns:
        List of (worktree_path, branch_ref) tuples.
    """
    entries: list[tuple[str, str]] = []
    wt_path = ""
    wt_branch = ""

    def flush() -> None:
        nonlocal wt_path, wt_branch
        if wt_path:
            entries.append((wt_path, wt_branch))
        wt_path = ""
        wt_branch = ""

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("worktree "):
            wt_path = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            wt_branch = line.split(" ", 1)[1]

    flush()
    return entries


def find_worktree_path_for_branch(
    run: Callable[[list[str]], str],
    branch_name: str,
) -> Path | None:
    """Find worktree path whose checked-out branch matches ``branch_name``.

    Returns:
        Path to the worktree, or None if not found.
    """
    if not branch_name:
        return None
    output = run(["worktree", "list", "--porcelain"])
    ref = f"refs/heads/{branch_name}"
    for wt_path, wt_branch in _parse_worktree_list(output):
        if wt_branch == ref:
            return Path(wt_path)
    return None


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

    for wt_path, wt_branch in _parse_worktree_list(output):
        if wt_branch != f"refs/heads/{branch_name}":
            continue
        if branch_name == current_branch:
            if wt_path and wt_path != current_worktree:
                return True
        elif wt_path:
            return True

    logger.bind(
        domain="git",
        action="is_branch_occupied_by_worktree",
        branch=branch_name,
        occupied=False,
    ).debug("Checked branch worktree occupation")
    return False


def get_worktrees_for_branch(
    run: Callable[[list[str]], str],
    branch_name: str,
) -> list[str]:
    """Return paths of worktrees that have the given branch checked out.

    Excludes the current worktree if it holds the branch (caller handles that).

    Args:
        run: Git command runner function
        branch_name: Branch name to look for

    Returns:
        List of worktree root paths (may be empty)
    """
    if not branch_name:
        return []

    current_worktree = get_worktree_root(run)
    current_branch = run(["branch", "--show-current"])
    output = run(["worktree", "list", "--porcelain"])
    ref = f"refs/heads/{branch_name}"

    occupied: list[str] = []
    for wt_path, wt_branch in _parse_worktree_list(output):
        if wt_branch != ref:
            continue
        if branch_name == current_branch:
            if wt_path and wt_path != current_worktree:
                occupied.append(wt_path)
        elif wt_path:
            occupied.append(wt_path)

    logger.bind(
        domain="git",
        action="get_worktrees_for_branch",
        branch=branch_name,
        count=len(occupied),
    ).debug("Found worktrees for branch")
    return occupied


def remove_worktree(wt_path: Path, force: bool = False) -> None:
    """Remove a worktree.

    Args:
        wt_path: Path to the worktree
        force: Force removal even if dirty

    Raises:
        GitError: If removal fails
    """
    import subprocess

    from vibe3.exceptions import GitError

    cmd = ["git", "worktree", "remove", str(wt_path)]
    if force:
        cmd.append("--force")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise GitError("worktree remove", result.stderr)

    logger.bind(
        domain="git",
        action="remove_worktree",
        path=str(wt_path),
    ).info("Removed worktree")
