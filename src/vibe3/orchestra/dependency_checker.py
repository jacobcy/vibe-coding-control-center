"""Dependency resolution checker for orchestra."""

import re
import time
from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient

_BLOCKED_BY_PATTERNS = [
    r"blocked\s+by\s+#(\d+)",
    r"depends\s+on\s+#(\d+)",
    r"requires\s+#(\d+)",
    r"blocked-by:\s*#(\d+)",
]

_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_MAX_SIZE = 200


def parse_blocked_by(body: str) -> list[int]:
    """Parse blocking issue numbers from issue body."""
    found: set[int] = set()
    lower = body.lower()
    for pattern in _BLOCKED_BY_PATTERNS:
        for match in re.finditer(pattern, lower):
            found.add(int(match.group(1)))
    return sorted(found)


class DependencyChecker:
    """Checks if all blocking issues for a given issue are resolved.

    Caches ``view_issue`` results for ``_CACHE_TTL_SECONDS`` to avoid
    redundant API calls when multiple issues share the same blockers.
    """

    def __init__(
        self,
        repo: str | None = None,
        github: GitHubClient | None = None,
    ) -> None:
        self.repo = repo
        self._github = github or GitHubClient()
        self._issue_cache: dict[int, tuple[float, dict[str, Any]]] = {}

    def _fetch_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Fetch issue data with TTL cache."""
        now = time.monotonic()

        cached = self._issue_cache.get(issue_number)
        if cached is not None:
            ts, data = cached
            if now - ts < _CACHE_TTL_SECONDS:
                return data

        result = self._github.view_issue(issue_number, repo=self.repo)
        if not result or result == "network_error":
            logger.bind(domain="orchestra").warning(
                f"Cannot fetch issue #{issue_number}"
            )
            return None
        if not isinstance(result, dict):
            return None

        # Bounded cache: evict oldest when full
        if len(self._issue_cache) >= _CACHE_MAX_SIZE:
            oldest_key = min(self._issue_cache, key=lambda k: self._issue_cache[k][0])
            del self._issue_cache[oldest_key]

        self._issue_cache[issue_number] = (now, result)
        return result

    def fetch_body(self, issue_number: int) -> str:
        """Fetch issue body via GitHubClient.view_issue()."""
        data = self._fetch_issue(issue_number)
        if data is None:
            return ""
        return str(data.get("body") or "")

    def is_closed(self, issue_number: int) -> bool:
        """Return True if the issue is closed. Conservatively False on error."""
        data = self._fetch_issue(issue_number)
        if data is None:
            return False
        return str(data.get("state", "OPEN")).upper() == "CLOSED"

    def all_resolved(self, blocking_issues: list[int]) -> bool:
        """Return True only when every blocking issue is closed."""
        return all(self.is_closed(n) for n in blocking_issues)

    def check(self, issue_number: int) -> tuple[bool, list[int]]:
        """Check whether an issue's dependencies are resolved.

        Returns:
            (all_resolved, blocking_numbers) tuple.
        """
        body = self.fetch_body(issue_number)
        blockers = parse_blocked_by(body)
        if not blockers:
            return True, []
        resolved = self.all_resolved(blockers)
        return resolved, blockers
