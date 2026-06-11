"""Flow context cache service for PR-related cache operations.

This service handles PR-specific cache updates in the flow context,
decoupling PR operations from issue-specific logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class FlowContextCacheService:
    """Service for PR-related flow context cache operations.

    This service handles PR-specific cache updates, separating PR concerns
    from issue-specific title caching logic.
    """

    def __init__(self, store: SQLiteClient) -> None:
        """Initialize the cache service.

        Args:
            store: SQLite client with context cache repo mixin.
        """
        self.store = store

    def update_pr(
        self,
        branch: str,
        pr_number: int,
        pr_title: str,
    ) -> None:
        """Update cache with PR information for a branch.

        Args:
            branch: The git branch name.
            pr_number: The PR number.
            pr_title: The PR title.
        """
        existing = self.store.get_flow_context_cache(branch)
        self.store.upsert_flow_context_cache(
            branch=branch,
            task_issue_number=existing.get("task_issue_number") if existing else None,
            issue_title=existing.get("issue_title") if existing else None,
            pr_number=pr_number,
            pr_title=pr_title,
        )
        logger.bind(
            domain="flow_context_cache",
            branch=branch,
            pr_number=pr_number,
        ).debug("Updated PR cache")

    def update_prs_bulk(
        self,
        prs: list[tuple[str, int, str]],
    ) -> None:
        """Bulk update cache with PR information for multiple branches.

        Args:
            prs: List of tuples (branch, pr_number, pr_title).
        """
        if not prs:
            return

        branches = [branch for branch, _, _ in prs]

        # Batch read existing cache entries
        existing_cache = self.store.get_flow_context_cache_bulk(branches)

        # Prepare bulk entries
        entries: list[tuple[str, int | None, str | None, int | None, str | None]] = []
        for branch, pr_number, pr_title in prs:
            existing = existing_cache.get(branch)
            entries.append(
                (
                    branch,
                    existing.get("task_issue_number") if existing else None,
                    existing.get("issue_title") if existing else None,
                    pr_number,
                    pr_title,
                )
            )

        # Single transaction for all updates
        self.store.upsert_flow_context_cache_bulk(entries)

        logger.bind(
            domain="flow_context_cache",
            count=len(prs),
        ).debug("Bulk updated PR cache")
