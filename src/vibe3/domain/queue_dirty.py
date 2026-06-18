"""Queue dirty signal management for cross-process coordination.

This module provides a lightweight file-based signaling mechanism for coordinating
between CLI commands (e.g., `task resume`) and the serve dispatch coordinator.

The marker file lives in the git common directory (.git/vibe3/queue_dirty) to ensure
visibility across all worktrees.
"""

from pathlib import Path

from vibe3.services.shared.paths import get_git_common_dir


def mark_queue_dirty(git_common_dir: str | None = None) -> None:
    """Write a marker file to signal that the dispatch queue needs maintenance.

    This is called by CLI commands (e.g., `task resume`) to notify the serve
    coordinator that the queue state has changed and should be refreshed.

    Args:
        git_common_dir: Optional git common directory path. If None, uses
            get_git_common_dir() to determine the path.
    """
    if git_common_dir is None:
        git_common_dir = get_git_common_dir()

    if not git_common_dir:
        return

    marker_path = Path(git_common_dir) / "vibe3" / "queue_dirty"

    # Create parent directory if needed
    marker_path.parent.mkdir(parents=True, exist_ok=True)

    # Write empty marker file
    marker_path.touch()


def is_queue_dirty(git_common_dir: str | None = None) -> bool:
    """Check if the queue dirty signal marker exists.

    Args:
        git_common_dir: Optional git common directory path. If None, uses
            get_git_common_dir() to determine the path.

    Returns:
        True if the marker file exists, False otherwise.
    """
    if git_common_dir is None:
        git_common_dir = get_git_common_dir()

    if not git_common_dir:
        return False

    marker_path = Path(git_common_dir) / "vibe3" / "queue_dirty"
    return marker_path.exists()


def clear_queue_dirty(git_common_dir: str | None = None) -> None:
    """Remove the queue dirty signal marker.

    This is called by the serve coordinator after consuming the signal.

    Args:
        git_common_dir: Optional git common directory path. If None, uses
            get_git_common_dir() to determine the path.
    """
    if git_common_dir is None:
        git_common_dir = get_git_common_dir()

    if not git_common_dir:
        return

    marker_path = Path(git_common_dir) / "vibe3" / "queue_dirty"

    # No-op if file doesn't exist
    if marker_path.exists():
        marker_path.unlink()
