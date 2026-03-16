"""Git client implementation."""

import subprocess
from typing import Protocol


class GitClientProtocol(Protocol):
    """Protocol for Git client."""

    def get_current_branch(self) -> str:
        """Get current branch name."""
        ...

    def get_worktree_name(self) -> str:
        """Get current worktree name."""
        ...


class GitClient:
    """Git client for interacting with git repository."""

    def get_current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Current branch name
        """
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_worktree_name(self) -> str:
        """Get current worktree name.

        Returns:
            Worktree name (last component of path)
        """
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("/")[-1]
