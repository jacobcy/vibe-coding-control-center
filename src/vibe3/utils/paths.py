"""Vibe3 path resolution utilities.

This module provides centralized path resolution for .git/vibe3/ directory structure.
These functions are intentionally kept in the utils layer (L6) to avoid upward
dependencies from clients and environment layers.
"""

from __future__ import annotations

from pathlib import Path


def get_vibe3_cache_path(repo_path: str | Path, filename: str) -> Path:
    """Get path to a vibe3 cache file under .git/vibe3/.

    Args:
        repo_path: Path to the repository root
        filename: Cache filename (e.g., "merged_prs.json", "recent_prs.json")

    Returns:
        Absolute path to the cache file

    Example:
        >>> get_vibe3_cache_path("/repo", "merged_prs.json")
        Path("/repo/.git/vibe3/merged_prs.json")
    """
    return Path(repo_path) / ".git" / "vibe3" / filename


def get_vibe3_db_path(git_dir: str | Path) -> Path:
    """Get path to handoff.db under .git/vibe3/.

    Args:
        git_dir: Path to .git directory (NOT repository root)

    Returns:
        Absolute path to handoff.db

    Example:
        >>> get_vibe3_db_path("/repo/.git")
        Path("/repo/.git/vibe3/handoff.db")
    """
    return Path(git_dir) / "vibe3" / "handoff.db"


def get_vibe3_log_dir(repo_path: str | Path) -> Path:
    """Get path to vibe3 log directory under .git/vibe3/logs/.

    Args:
        repo_path: Path to the repository root

    Returns:
        Absolute path to the log directory

    Example:
        >>> get_vibe3_log_dir("/repo")
        Path("/repo/.git/vibe3/logs")
    """
    return Path(repo_path) / ".git" / "vibe3" / "logs"
