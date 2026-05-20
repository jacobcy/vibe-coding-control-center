"""Helpers for listing Git branches with commit timestamps."""

from collections.abc import Callable

from loguru import logger

from vibe3.exceptions import GitError


def get_all_branches_with_timestamps(
    runner: Callable[[list[str]], str], remote: bool = False
) -> list[dict[str, str]]:
    """Get local or remote branches with last commit timestamps."""
    try:
        if remote:
            args = [
                "branch",
                "-r",
                "--list",
                "origin/*",
                "--format=%(refname:short) %(committerdate:iso8601)",
            ]
        else:
            args = [
                "branch",
                "--list",
                "*",
                "--format=%(refname:short) %(committerdate:iso8601)",
            ]
        output = runner(args)
    except GitError as exc:
        logger.error(f"Failed to get branches: {exc}")
        return []

    branches: list[dict[str, str]] = []
    for line in output.strip().splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        branch, timestamp = parts
        branches.append({"branch": branch, "timestamp": timestamp})
    return branches
