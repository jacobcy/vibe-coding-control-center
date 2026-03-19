"""Git helper utilities."""

import subprocess

from vibe3.exceptions import GitError


def get_commit_message(sha: str) -> str:
    """Get commit message for a given SHA.

    Args:
        sha: Commit SHA (full or short)

    Returns:
        Commit message string

    Raises:
        GitError: If unable to get commit message
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(
            operation="log",
            details=f"Failed to get commit message for {sha}: {e.stderr}",
        ) from e


def get_current_branch() -> str:
    """Get current git branch name.

    Returns:
        Branch name string

    Raises:
        GitError: If unable to get current branch
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(
            operation="rev-parse", details=f"Failed to get current branch: {e.stderr}"
        ) from e
