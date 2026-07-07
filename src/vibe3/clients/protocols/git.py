"""GitPathProtocol — Protocol for Git path-related operations.

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.git import GitPathProtocol

"""

from pathlib import Path
from typing import Protocol


class GitPathProtocol(Protocol):
    """Protocol for Git path-related operations."""

    def get_git_common_dir(self) -> str: ...
    def get_worktree_root(self) -> str: ...
    def find_worktree_path_for_branch(self, branch: str) -> Path | None: ...
    def get_current_branch(self) -> str: ...


__all__ = ["GitPathProtocol"]
