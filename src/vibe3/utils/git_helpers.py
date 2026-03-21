"""Git helper utilities."""

import hashlib
import subprocess
from pathlib import Path

from vibe3.exceptions import GitError


def get_branch_handoff_dir(git_dir: str, branch: str) -> Path:
    """Get handoff directory for a specific branch.

    Creates a unique directory path for branch handoff files, using sanitized
    branch name with hash suffix to prevent collisions.

    Args:
        git_dir: Path to .git directory
        branch: Branch name

    Returns:
        Path to .git/vibe3/handoff/<branch-safe>-<hash>/

    Example:
        >>> get_branch_handoff_dir(".git", "feature/api-v2")
        Path(".git/vibe3/handoff/feature-api-v2-a1b2c3d4")
    """
    # Sanitize branch name with hash suffix to prevent collisions
    # Example: feature/api-v2 and feature/api/v2 would otherwise collide
    branch_hash = hashlib.sha256(branch.encode()).hexdigest()[:8]
    # Replace path separators, remove leading/trailing special chars
    branch_safe = branch.replace("/", "-").replace("\\", "-").strip("-_.")
    # Fallback if branch name becomes empty after sanitization
    if not branch_safe:
        branch_safe = "default"
    # Append hash suffix for uniqueness
    branch_dir = f"{branch_safe}-{branch_hash}"

    return Path(git_dir) / "vibe3" / "handoff" / branch_dir


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
