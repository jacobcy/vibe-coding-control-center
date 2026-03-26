"""Git branch utilities for finding parent branches."""

import subprocess

from loguru import logger


def find_parent_branch(current_branch: str | None = None) -> str | None:
    """Find the closest parent branch for the current branch.

    This function analyzes the git branch topology to find the most likely
    parent branch - the branch that the current branch was forked from.

    The algorithm:
    1. Get all local and remote branches
    2. Calculate merge-base and commit distance for each branch
    3. Return the branch with minimum commits (closest parent)

    Args:
        current_branch: Current branch name (optional, auto-detected if None)

    Returns:
        Parent branch name (e.g., "feature/A", "origin/main") or None if not found

    Example:
        Given: main → feature/A → refactor/B (current)
        Returns: feature/A (not main)
    """
    try:
        # Get current branch if not provided
        if not current_branch:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

        # Get all branches
        result = subprocess.run(
            ["git", "branch", "-a", "--format=%(refname:short)"],
            capture_output=True,
            text=True,
            check=True,
        )
        all_branches = [b.strip() for b in result.stdout.splitlines() if b.strip()]

        # Exclude current branch and HEAD
        candidates = [
            b for b in all_branches if b != current_branch and not b.startswith("HEAD")
        ]

        # Calculate distance for each candidate
        distances: list[tuple[str, int]] = []
        for branch in candidates:
            try:
                # Get merge-base
                base_result = subprocess.run(
                    ["git", "merge-base", branch, current_branch],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                merge_base = base_result.stdout.strip()

                # Count commits from merge-base to current branch
                count_result = subprocess.run(
                    ["git", "rev-list", "--count", f"{merge_base}..{current_branch}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                count = int(count_result.stdout.strip())

                # Only consider branches with commits ahead
                if count > 0:
                    distances.append((branch, count))

            except subprocess.CalledProcessError:
                continue

        # Sort by distance (ascending) and return closest
        if distances:
            distances.sort(key=lambda x: x[1])
            parent = distances[0][0]
            logger.bind(
                domain="git",
                action="find_parent_branch",
                current_branch=current_branch,
                parent_branch=parent,
                distance=distances[0][1],
            ).info("Found parent branch")
            return parent

        logger.bind(
            domain="git",
            action="find_parent_branch",
            current_branch=current_branch,
        ).warning("No parent branch found")
        return None

    except Exception as e:
        logger.bind(
            domain="git",
            action="find_parent_branch",
            error=str(e),
        ).error("Failed to find parent branch")
        return None
