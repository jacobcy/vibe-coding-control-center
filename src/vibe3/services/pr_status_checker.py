"""PR Status Checker — authoritative truth for issue completion status.

This module provides the ONLY source of truth for determining if work on an issue
is complete: checking if there's a merged PR.

Do NOT rely on:
- state/done labels (can be manually added/removed)
- local flow records (are cache, not source of truth)
"""

from typing import Any, cast

from loguru import logger

from vibe3.clients.github_issues_ops import parse_linked_issues


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
    from vibe3.clients.github_client import GitHubClient

    github_client = GitHubClient()

    # Query merged PRs and check if any reference this issue
    # Note: This is authoritative truth from GitHub, not local state
    try:
        merged_prs = github_client.list_merged_prs(limit=100)

        for pr in merged_prs:
            if not isinstance(pr, dict):
                continue

            # Parse PR body for linked issues
            body = pr.get("body") or ""
            linked_issues = parse_linked_issues(body)

            if issue_number in linked_issues:
                logger.bind(
                    domain="pr_status",
                    issue_number=issue_number,
                    pr_number=pr.get("number"),
                ).debug("Found merged PR for issue")
                return True

        logger.bind(domain="pr_status", issue_number=issue_number).debug(
            "No merged PR found for issue"
        )
        return False

    except Exception as exc:
        logger.bind(
            domain="pr_status", issue_number=issue_number, error=str(exc)
        ).warning("Failed to check merged PR status, assuming not merged")
        return False


def get_merged_pr_for_issue(
    issue_number: int, repo: str | None = None
) -> dict[str, Any] | None:
    """Get the merged PR associated with an issue (if any).

    Args:
        issue_number: GitHub issue number
        repo: Repository (owner/repo format, optional, for future use)

    Returns:
        PR dict with keys: number, headRefName, body, mergedAt
        Returns None if no merged PR found
    """
    from vibe3.clients.github_client import GitHubClient

    github_client = GitHubClient()

    try:
        merged_prs = github_client.list_merged_prs(limit=100)

        for pr in merged_prs:
            if not isinstance(pr, dict):
                continue

            body = pr.get("body") or ""
            linked_issues = parse_linked_issues(body)

            if issue_number in linked_issues:
                return cast(dict[str, Any], pr)

        return None

    except Exception:
        return None
