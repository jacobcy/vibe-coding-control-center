"""Queue dirty signal management for cross-process coordination.

This module provides a lightweight file-based signaling mechanism for coordinating
between CLI commands (e.g., `task resume`) and the serve dispatch coordinator.

The marker file lives in the git common directory (.git/vibe3/queue_dirty) to ensure
visibility across all worktrees.
"""

from pathlib import Path

from loguru import logger

from vibe3.clients import GitClient

_MARKER_SUBDIR = "vibe3"
_MARKER_FILENAME = "queue_dirty"


def _resolve_git_common_dir(git_common_dir: str | None) -> str | None:
    """Resolve git common directory from explicit arg or GitClient."""
    if git_common_dir is not None:
        return git_common_dir
    try:
        return GitClient().get_git_common_dir()
    except (OSError, ValueError):
        return None


def _marker_path(git_common_dir: str) -> Path:
    return Path(git_common_dir) / _MARKER_SUBDIR / _MARKER_FILENAME


def mark_queue_dirty(git_common_dir: str | None = None) -> None:
    """Write a marker file to signal that the dispatch queue needs maintenance.

    Called by CLI commands (e.g., ``task resume``) to notify the serve
    coordinator that the queue state has changed and should be refreshed.
    """
    resolved = _resolve_git_common_dir(git_common_dir)
    if not resolved:
        return

    path = _marker_path(resolved)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()

    logger.bind(domain="queue_dirty", action="mark").debug("Queue dirty signal written")


def is_queue_dirty(git_common_dir: str | None = None) -> bool:
    """Check if the queue dirty signal marker exists."""
    resolved = _resolve_git_common_dir(git_common_dir)
    if not resolved:
        return False

    return _marker_path(resolved).exists()


def clear_queue_dirty(git_common_dir: str | None = None) -> None:
    """Remove the queue dirty signal marker.

    Called by the serve coordinator after consuming the signal.
    No-op if marker doesn't exist.
    """
    resolved = _resolve_git_common_dir(git_common_dir)
    if not resolved:
        return

    path = _marker_path(resolved)
    if path.exists():
        path.unlink()
