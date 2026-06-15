"""PR Status Checker — authoritative truth for issue completion status.

This module provides the ONLY source of truth for determining if work on an issue
is complete: checking if there's a merged PR.

Do NOT rely on:
- state/done labels (can be manually added/removed)
- local flow records (are cache, not source of truth)

This module lives in vibe3.clients because it only depends on client-layer
dependencies (GitHubClient, MergedPRCache, GitClient) and stdlib.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients import GitClient, GitHubClient, MergedPRCache


def _resolve_repo_path() -> Path:
    """Resolve the repository root path for cache operations."""
    try:
        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except (OSError, ValueError):
        pass
    return Path.cwd()


def get_merged_pr_for_issue(
    issue_number: int, repo: str | None = None
) -> dict[str, Any] | None:
    """Get the merged PR associated with an issue (if any).

    This is the ONLY source of truth for determining if work is complete.
    Use this instead of checking state/done labels or flow_status.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional, for future use)

    Returns:
        PR dict with keys: number, headRefName, body, mergedAt
        Returns None if no merged PR found or query failed

    Example:
        >>> pr = get_merged_pr_for_issue(123)
        >>> if pr:
        ...     print(f"Issue #123 has merged PR #{pr['number']}")
    """
    repo_path = _resolve_repo_path()

    # Step 1: Check cache first
    cache = MergedPRCache(repo_path)
    cached_pr = cache.get_merged_pr_for_issue(issue_number)
    if cached_pr:
        logger.bind(
            domain="pr_status",
            issue_number=issue_number,
            pr_number=cached_pr.get("number"),
            source="cache",
        ).debug("Found merged PR for issue in cache")
        return cached_pr

    # Step 2: Cache miss - sync cache with latest merged PRs
    github_client = GitHubClient()
    logger.bind(
        domain="pr_status",
        issue_number=issue_number,
    ).debug("Cache miss, syncing cache")

    try:
        cache.sync(github_client, limit=200)

        cached_pr = cache.get_merged_pr_for_issue(issue_number)
        if cached_pr:
            logger.bind(
                domain="pr_status",
                issue_number=issue_number,
                pr_number=cached_pr.get("number"),
                source="sync",
            ).debug("Found merged PR for issue after sync")
            return cached_pr

        logger.bind(domain="pr_status", issue_number=issue_number).debug(
            "No merged PR found for issue"
        )
        return None

    except Exception as exc:
        logger.bind(
            domain="pr_status",
            issue_number=issue_number,
            error=str(exc),
            exc_info=True,
        ).warning(f"Failed to check merged PR status for issue #{issue_number}")
        return None


def has_merged_pr_for_issue(issue_number: int, repo: str | None = None) -> bool:
    """Check if an issue has a merged PR (authoritative truth).

    This is the ONLY source of truth for determining if work is complete.
    Use this instead of checking state/done labels or flow_status.

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional, for future use)

    Returns:
        True if issue has at least one merged PR, False otherwise

    Example:
        >>> has_merged_pr_for_issue(123)
        True  # Issue #123 has a merged PR, cannot be resumed
    """
    return get_merged_pr_for_issue(issue_number, repo) is not None
