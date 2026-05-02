"""Git path operations protocol and wrappers."""

from pathlib import Path
from typing import Protocol


class GitPathProtocol(Protocol):
    """Protocol for Git path-related operations."""

    def get_git_common_dir(self) -> str: ...
    def get_worktree_root(self) -> str: ...
    def find_worktree_path_for_branch(self, branch: str) -> Path | None: ...
    def get_current_branch(self) -> str: ...


def _get_git_client(git_client: GitPathProtocol | None = None) -> GitPathProtocol:
    """Get or create a GitClient instance."""
    if git_client is None:
        from vibe3.clients.git_client import GitClient

        return GitClient()
    return git_client


def get_git_common_dir(git_client: GitPathProtocol | None = None) -> str:
    """Get the shared git common directory (.git/)."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_git_common_dir()
    except (OSError, ValueError):
        return ""


def get_worktree_root(git_client: GitPathProtocol | None = None) -> str:
    """Get the current worktree root."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.get_worktree_root()
    except (OSError, ValueError):
        return ""


def find_worktree_path_for_branch(
    branch: str, git_client: GitPathProtocol | None = None
) -> Path | None:
    """Find the worktree path for a specific branch."""
    git_client = _get_git_client(git_client)
    try:
        return git_client.find_worktree_path_for_branch(branch)
    except (OSError, ValueError):
        return None
