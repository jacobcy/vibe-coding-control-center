"""Branch-level lock for vibe3 check operations.

Prevents concurrent check operations on the same branch across multiple
worktrees or processes on the same machine.
"""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from vibe3.clients import GitClient


@contextmanager
def check_lock(branch: str, git_client: "GitClient") -> Generator[bool, None, None]:
    """Acquire branch-level lock for vibe3 check. Non-blocking.

    Args:
        branch: Branch name to lock
        git_client: Git client for resolving git common dir

    Yields:
        True if lock acquired, False if lock held by another process

    Note:
        Uses fcntl.flock which is not available on Windows.
        Lock is automatically released on process exit.
    """
    # Determine lock directory from git common dir
    git_common_dir = git_client.get_git_common_dir()
    if not git_common_dir:
        # Fallback to .git in current directory
        git_common_dir = ".git"

    locks_dir = Path(git_common_dir) / "vibe3" / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize branch name for filesystem
    # Replace problematic characters with underscores
    safe_branch = branch.replace("/", "_").replace("\\", "_").replace(":", "_")
    lock_file = locks_dir / f"check-{safe_branch}.lock"

    # Try to acquire lock (non-blocking)
    lock_fd = None
    acquired = False

    try:
        lock_fd = open(lock_file, "w")
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (IOError, OSError):
            # Lock held by another process
            acquired = False

        yield acquired
    finally:
        if lock_fd is not None:
            try:
                if acquired:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except (IOError, OSError):
                # Ignore errors during cleanup
                pass
