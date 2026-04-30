"""Persistent cache for merged PR status.

This module provides a file-based cache for merged PR data to eliminate
redundant GitHub API calls. The cache stores issue→merged-PR mappings in
.git/vibe3/merged_prs.json.

Note: This cache is distinct from the in-memory branch→PR cache in
check_service.py's _initialize_pr_cache(). That cache is for check verification,
while this cache persists merged PR status for issue completion checks.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.github_issues_ops import parse_linked_issues


class MergedPRCache:
    """Persistent cache for merged PR data.

    The cache file structure:
    {
      "last_sync": "2024-01-15T10:00:00Z",
      "prs": {
        "123": {
          "number": 123,
          "headRefName": "feature/foo",
          "body": "Closes #456",
          "mergedAt": "2024-01-10T...",
          "issue": 456,
        },
        ...
      }
    }
    """

    CACHE_FILE = ".git/vibe3/merged_prs.json"

    def __init__(self, repo_path: Path) -> None:
        """Initialize cache with repository path.

        Args:
            repo_path: Path to the repository root (where .git/ is located)
        """
        self.repo_path = repo_path
        self.cache_file = repo_path / self.CACHE_FILE

    def _ensure_dir(self) -> None:
        """Ensure cache directory exists."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> dict[str, Any]:
        """Load cache from file.

        Returns empty structure if cache doesn't exist or is corrupted.
        """
        try:
            with open(self.cache_file) as f:
                data = json.load(f)
                # Validate structure
                if (
                    isinstance(data, dict)
                    and "prs" in data
                    and isinstance(data.get("prs"), dict)
                ):
                    return data
        except FileNotFoundError:
            logger.bind(domain="merged_pr_cache").debug(
                "Cache file not found, starting fresh"
            )
        except json.JSONDecodeError as e:
            logger.bind(domain="merged_pr_cache", error=str(e)).warning(
                "Cache file corrupted, starting fresh"
            )

        # Return empty structure
        return {"last_sync": None, "prs": {}}

    def _save_cache(self, data: dict[str, Any]) -> None:
        """Save cache to file.

        Args:
            data: Cache data structure
        """
        self._ensure_dir()
        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_merged_pr_for_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Get merged PR for an issue from cache.

        Args:
            issue_number: GitHub issue number

        Returns:
            PR dict with keys: number, headRefName, body, mergedAt, issue
            Returns None if issue not in cache
        """
        cache = self._load_cache()
        prs = cache.get("prs", {})

        # Linear scan for matching issue
        for pr_data in prs.values():
            if isinstance(pr_data, dict) and pr_data.get("issue") == issue_number:
                logger.bind(
                    domain="merged_pr_cache",
                    issue_number=issue_number,
                    pr_number=pr_data.get("number"),
                ).debug("Cache hit for issue")
                return pr_data

        logger.bind(domain="merged_pr_cache", issue_number=issue_number).debug(
            "Cache miss for issue"
        )
        return None

    def sync(self, github_client: Any, limit: int = 200) -> int:
        """Sync cache with latest merged PRs from GitHub.

        Fetches the most recent N merged PRs and merges new entries into cache.
        Existing entries are not modified.

        Args:
            github_client: GitHub client with list_merged_prs() method
            limit: Maximum number of PRs to fetch

        Returns:
            Number of new PRs added to cache
        """
        logger.bind(domain="merged_pr_cache", limit=limit).info(
            "Syncing merged PR cache"
        )

        try:
            merged_prs = github_client.list_merged_prs(limit=limit)
        except Exception as exc:
            logger.bind(
                domain="merged_pr_cache",
                error=str(exc),
                exc_info=True,
            ).error("Failed to fetch merged PRs")
            return 0

        cache = self._load_cache()
        prs = cache.get("prs", {})

        new_count = 0
        for pr in merged_prs:
            if not isinstance(pr, dict):
                continue

            pr_number = str(pr.get("number"))
            if pr_number in prs:
                # Already cached, skip
                continue

            # Parse linked issues from body
            body = pr.get("body") or ""
            linked_issues = parse_linked_issues(body)

            # Store first linked issue as the task issue
            if linked_issues:
                # Store full PR dict with issue field added
                prs[pr_number] = {
                    "number": pr["number"],
                    "headRefName": pr.get("headRefName"),
                    "body": body,
                    "mergedAt": pr.get("mergedAt"),
                    "issue": linked_issues[0],
                }
                new_count += 1

        cache["prs"] = prs
        cache["last_sync"] = datetime.now(timezone.utc).isoformat()
        self._save_cache(cache)

        logger.bind(domain="merged_pr_cache", new_prs=new_count).info(
            "Cache sync complete"
        )
        return new_count

    def rebuild(self, github_client: Any) -> int:
        """Rebuild cache from scratch with all merged PRs.

        Fetches all merged PRs (limit=None) and replaces the entire cache.

        Args:
            github_client: GitHub client with list_merged_prs() method

        Returns:
            Total number of PRs with linked issues added to cache
        """
        logger.bind(domain="merged_pr_cache").info("Rebuilding merged PR cache")

        try:
            merged_prs = github_client.list_merged_prs(limit=None)
        except Exception as exc:
            logger.bind(
                domain="merged_pr_cache",
                error=str(exc),
                exc_info=True,
            ).error("Failed to fetch merged PRs for rebuild")
            return 0

        prs: dict[str, Any] = {}
        count = 0

        for pr in merged_prs:
            if not isinstance(pr, dict):
                continue

            pr_number = str(pr.get("number"))

            # Parse linked issues from body
            body = pr.get("body") or ""
            linked_issues = parse_linked_issues(body)

            # Store first linked issue as the task issue
            if linked_issues:
                # Store full PR dict with issue field added
                prs[pr_number] = {
                    "number": pr["number"],
                    "headRefName": pr.get("headRefName"),
                    "body": body,
                    "mergedAt": pr.get("mergedAt"),
                    "issue": linked_issues[0],
                }
                count += 1

        cache = {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "prs": prs,
        }
        self._save_cache(cache)

        logger.bind(domain="merged_pr_cache", total_prs=count).info(
            "Cache rebuild complete"
        )
        return count
