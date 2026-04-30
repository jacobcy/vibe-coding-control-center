"""PR Status Checker — authoritative truth for issue completion status.

This module provides the ONLY source of truth for determining if work on an issue
is complete: checking if there's a merged PR.

Do NOT rely on:
- state/done labels (can be manually added/removed)
- local flow records (are cache, not source of truth)
"""

from pathlib import Path
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.clients.merged_pr_cache import MergedPRCache
from vibe3.utils.path_helpers import get_git_common_dir


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
    # Step 1: Resolve repo path for cache
    try:
        git_common_dir = get_git_common_dir()
        if git_common_dir:
            repo_path = Path(git_common_dir).parent
        else:
            # Fallback to cwd if git common dir unavailable
            repo_path = Path.cwd()
    except Exception:
        repo_path = Path.cwd()

    # Step 2: Check cache first
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

    # Step 3: Cache miss - sync cache with latest merged PRs
    github_client = GitHubClient()
    logger.bind(
        domain="pr_status",
        issue_number=issue_number,
    ).debug("Cache miss, syncing cache")

    try:
        cache.sync(github_client, limit=200)

        # Step 4: Check cache again after sync
        cached_pr = cache.get_merged_pr_for_issue(issue_number)
        if cached_pr:
            logger.bind(
                domain="pr_status",
                issue_number=issue_number,
                pr_number=cached_pr.get("number"),
                source="sync",
            ).debug("Found merged PR for issue after sync")
            return cached_pr

        # Step 5: Fall through to direct API call (defense-in-depth)
        merged_prs = github_client.list_merged_prs(limit=100)

        for pr in merged_prs:
            if not isinstance(pr, dict):
                continue

            body = pr.get("body") or ""
            linked_issues = parse_linked_issues(body)

            if issue_number in linked_issues:
                logger.bind(
                    domain="pr_status",
                    issue_number=issue_number,
                    pr_number=pr.get("number"),
                    source="api",
                ).debug("Found merged PR for issue via API")
                return cast(dict[str, Any], pr)

        logger.bind(domain="pr_status", issue_number=issue_number).debug(
            "No merged PR found for issue"
        )
        return None

    except Exception as exc:
        logger.bind(
            domain="pr_status",
            issue_number=issue_number,
            error=str(exc),
            exc_info=True,  # Record full exception
        ).error("Failed to check merged PR status")
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
