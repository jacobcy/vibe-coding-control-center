"""Git branch utilities for finding parent branches."""

import subprocess

from loguru import logger


def _run_git(args: list[str]) -> str:
    """Run a git command and return stripped stdout.

    Raises subprocess.CalledProcessError on non-zero exit.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def find_parent_branch(current_branch: str | None = None) -> str | None:
    """Find the closest parent branch for the current branch.

    This function analyzes the git branch topology to find the most likely
    parent branch - the branch that the current branch was forked from.

    The algorithm walks the current branch history from newest to oldest and
    returns the first local branch (other than the current one) that contains
    a commit but not the current tip. That commit is the merge-base with the
    closest parent, so its distance from the tip is the minimum positive
    commit count - exactly the "closest parent" semantics.

    This costs O(N) ``git for-each-ref`` calls where N is how far the current
    branch is ahead of its parent (typically a handful), instead of O(K) calls
    where K is the total number of local branches. With hundreds of stale local
    branches the old O(K) loop spawned hundreds of subprocesses (~40s); this
    version resolves the same parent in well under a second.

    Args:
        current_branch: Current branch name (optional, auto-detected if None)

    Returns:
        Parent branch name (e.g., "feature/A") or None if not found

    Example:
        Given: main -> feature/A -> refactor/B (current)
        Returns: feature/A (not main)
    """
    try:
        # Get current branch if not provided
        if not current_branch:
            current_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])

        # Resolve the current tip so we can exclude branches that already
        # contain it (those have commit distance 0 and are not "parents").
        tip = _run_git(["rev-parse", current_branch])

        # Commits reachable from current, newest first.
        commits = _run_git(["rev-list", current_branch]).splitlines()

        # Walk from the commit just below the tip toward the root. The first
        # commit contained by some other local branch (but not by the current
        # tip) marks the merge-base with the closest parent.
        for index, commit in enumerate(commits):
            if index == 0:
                # Skip the tip itself; a parent must be strictly behind it.
                continue

            refs = _run_git(
                [
                    "for-each-ref",
                    "--format=%(refname:short)",
                    "--contains",
                    commit,
                    "--no-contains",
                    tip,
                    "refs/heads",
                ]
            ).splitlines()

            candidates = sorted(
                ref.strip()
                for ref in refs
                if ref.strip()
                and ref.strip() != current_branch
                and not ref.strip().startswith("HEAD")
            )

            if candidates:
                parent = candidates[0]
                logger.bind(
                    domain="git",
                    action="find_parent_branch",
                    current_branch=current_branch,
                    parent_branch=parent,
                    distance=index,
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
