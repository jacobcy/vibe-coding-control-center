"""Unified issue title cache service.

Provides a single source of truth for issue title caching across all commands.

IMPORTANT: All methods use 'branch' as the standard parameter.
Issue number conversion should ONLY happen at command layer, not in cache service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient


class IssueTitleCacheService:
    """Unified service for issue title caching.

    Abstracts away the branch-based cache storage.

    Key design decisions:
    - Primary key in DB is 'branch'
    - All methods use 'branch' as parameter (standard)
    - Issue number conversion happens at command layer, not here
    - Cache is updated on flow init, PR creation, and title fetch
    """

    def __init__(
        self,
        store: SQLiteClient,
        github_client: GitHubClient | None = None,
    ) -> None:
        """Initialize the cache service.

        Args:
            store: SQLite client with context cache repo mixin.
            github_client: Optional GitHub client for cache misses.
                          If None, will be lazy-initialized when needed.
        """
        self.store = store
        self._github_client = github_client

    @property
    def github_client(self) -> GitHubClient:
        """Lazy-initialized GitHub client."""
        if self._github_client is None:
            from vibe3.clients.github_client import GitHubClient

            self._github_client = GitHubClient()
        return self._github_client

    # ============================================================
    # Public API - Read Operations (all use branch parameter)
    # ============================================================

    def get_title(self, branch: str) -> str | None:
        """Get cached title for a branch.

        Args:
            branch: The git branch name (standard parameter).

        Returns:
            Cached title if found, None otherwise.
        """
        cache = self.store.get_flow_context_cache(branch)
        return cache.get("issue_title") if cache else None

    def get_titles(self, branches: list[str]) -> dict[str, str]:
        """Get cached titles for multiple branches.

        Args:
            branches: List of git branch names.

        Returns:
            Dict mapping branch -> title for cached entries only.
        """
        result: dict[str, str] = {}
        for branch in branches:
            title = self.get_title(branch)
            if title:
                result[branch] = title
        return result

    def get_title_with_fallback(
        self,
        branch: str,
    ) -> tuple[str | None, bool]:
        """Get title with cache-first strategy.

        First checks cache, then falls back to GitHub API if missing.
        Updates cache on successful API fetch.

        Args:
            branch: The git branch name (standard parameter).

        Returns:
            Tuple of (title, had_network_error).
            title is None if both cache and API fail.
        """
        # Try cache first
        cached_title = self.get_title(branch)
        if cached_title:
            return cached_title, False

        # Fall back to GitHub
        return self._fetch_and_cache_title(branch)

    def get_titles_with_fallback(
        self,
        branches: list[str],
    ) -> tuple[dict[str, str], bool]:
        """Get titles for multiple branches with cache-first strategy.

        Args:
            branches: List of git branch names.

        Returns:
            Tuple of (titles_dict, had_network_error).
        """
        titles: dict[str, str] = {}
        network_error = False

        # Batch get from cache
        cached_titles = self.get_titles(branches)
        titles.update(cached_titles)

        # Identify cache misses
        cache_misses = [b for b in branches if b not in titles]

        if cache_misses:
            logger.bind(
                domain="issue_title_cache",
                action="get_titles_with_fallback",
                cache_misses=cache_misses,
            ).debug(f"Fetching {len(cache_misses)} branches from GitHub")

            for branch in cache_misses:
                fetched_title, err = self._fetch_and_cache_title(branch)
                if fetched_title:
                    titles[branch] = fetched_title
                if err:
                    network_error = True

        return titles, network_error

    # ============================================================
    # Public API - Write Operations
    # ============================================================

    def update_title(
        self,
        branch: str,
        title: str,
    ) -> None:
        """Update cache with issue title for a branch.

        Args:
            branch: The git branch name.
            title: The issue title to cache.
        """
        existing = self.store.get_flow_context_cache(branch)
        self.store.upsert_flow_context_cache(
            branch=branch,
            task_issue_number=existing.get("task_issue_number") if existing else None,
            issue_title=title,
            pr_number=existing.get("pr_number") if existing else None,
            pr_title=existing.get("pr_title") if existing else None,
        )
        logger.bind(
            domain="issue_title_cache",
            branch=branch,
        ).debug("Updated title cache")

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
            domain="issue_title_cache",
            branch=branch,
            pr_number=pr_number,
        ).debug("Updated PR cache")

    def invalidate(self, branch: str) -> None:
        """Invalidate cache entry for a branch.

        Sets issue_title to NULL for the branch.

        Args:
            branch: The git branch name.
        """
        existing = self.store.get_flow_context_cache(branch)
        if existing:
            self.store.upsert_flow_context_cache(
                branch=branch,
                task_issue_number=existing.get("task_issue_number"),
                issue_title=None,  # Clear title
                pr_number=existing.get("pr_number"),
                pr_title=existing.get("pr_title"),
            )

    # ============================================================
    # Internal - GitHub Fallback
    # ============================================================

    def _fetch_and_cache_title(
        self,
        branch: str,
    ) -> tuple[str | None, bool]:
        """Fetch title from GitHub and update cache.

        Args:
            branch: The git branch name.

        Returns:
            Tuple of (title, had_network_error).
        """
        # Get issue number from cache
        cache = self.store.get_flow_context_cache(branch)
        if not cache:
            return None, False

        issue_number = cache.get("task_issue_number")
        if not issue_number:
            return None, False

        try:
            issue = self.github_client.view_issue(issue_number)
            if isinstance(issue, dict):
                title = issue.get("title", f"Issue #{issue_number}")
                self.update_title(branch, title)

                logger.bind(
                    domain="issue_title_cache",
                    action="fetch_and_cache",
                    branch=branch,
                    issue_number=issue_number,
                ).debug(f"Fetched and cached title for branch {branch}")

                return title, False

            elif issue == "network_error":
                return None, True

        except Exception as e:
            logger.bind(
                domain="issue_title_cache",
                action="fetch_and_cache",
                branch=branch,
                error=str(e),
            ).warning(f"Failed to fetch issue for branch {branch}")

        return None, True
