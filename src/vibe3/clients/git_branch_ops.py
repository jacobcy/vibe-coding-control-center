"""Git branch operations.

This module provides branch-related git operations extracted from GitClient.
"""

import subprocess

from loguru import logger

from vibe3.exceptions import GitError


def _run_git(args: list[str]) -> str:
    """Execute git command.

    Args:
        args: git subcommand and arguments

    Returns:
        Command stdout

    Raises:
        GitError: git command failed
    """
    cmd = ["git", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(" ".join(args), e.stderr.strip()) from e


def create_branch(branch_name: str, start_ref: str = "origin/main") -> None:
    """Create a new branch from start_ref.

    Args:
        branch_name: Name of the new branch
        start_ref: Starting reference (default: origin/main)
    """
    _run_git(["checkout", "-b", branch_name, start_ref])
    logger.bind(
        domain="git", action="create_branch", branch=branch_name, start_ref=start_ref
    ).info("Created branch")


def switch_branch(branch_name: str) -> None:
    """Switch to existing branch.

    Args:
        branch_name: Branch to switch to
    """
    _run_git(["checkout", branch_name])
    logger.bind(domain="git", action="switch_branch", branch=branch_name).info(
        "Switched branch"
    )


def delete_branch(branch_name: str, force: bool = False) -> None:
    """Delete local branch.

    Args:
        branch_name: Branch to delete
        force: Force delete even if not merged
    """
    flag = "-D" if force else "-d"
    _run_git(["branch", flag, branch_name])
    logger.bind(
        domain="git", action="delete_branch", branch=branch_name, force=force
    ).info("Deleted local branch")


def delete_remote_branch(branch_name: str) -> None:
    """Delete remote branch.

    Args:
        branch_name: Remote branch to delete
    """
    _run_git(["push", "origin", "--delete", branch_name])
    logger.bind(domain="git", action="delete_remote_branch", branch=branch_name).info(
        "Deleted remote branch"
    )


def get_merge_base(branch1: str, branch2: str) -> str:
    """Get merge base between two branches.

    Args:
        branch1: First branch
        branch2: Second branch

    Returns:
        Merge base commit SHA
    """
    return _run_git(["merge-base", branch1, branch2])


def branch_exists(branch_name: str) -> bool:
    """Check if branch exists.

    Args:
        branch_name: Branch name to check

    Returns:
        True if branch exists
    """
    try:
        _run_git(["rev-parse", "--verify", branch_name])
        return True
    except GitError as e:
        logger.debug(f"Branch check failed: {e}")
        return False
