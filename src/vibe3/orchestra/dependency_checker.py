"""Dependency resolution checker for orchestra."""

import re

from loguru import logger

from vibe3.clients.github_client import GitHubClient

_BLOCKED_BY_PATTERNS = [
    r"blocked\s+by\s+#(\d+)",
    r"depends\s+on\s+#(\d+)",
    r"requires\s+#(\d+)",
    r"blocked-by:\s*#(\d+)",
]


def parse_blocked_by(body: str) -> list[int]:
    """Parse blocking issue numbers from issue body."""
    found: set[int] = set()
    lower = body.lower()
    for pattern in _BLOCKED_BY_PATTERNS:
        for match in re.finditer(pattern, lower):
            found.add(int(match.group(1)))
    return sorted(found)


class DependencyChecker:
    """Checks if all blocking issues for a given issue are resolved."""

    def __init__(self, repo: str | None = None) -> None:
        self.repo = repo
        self._github = GitHubClient()

    def fetch_body(self, issue_number: int) -> str:
        """Fetch issue body via GitHubClient.view_issue()."""
        data = self._github.view_issue(issue_number)
        if not data or data == "network_error":
            logger.bind(domain="orchestra").warning(
                f"Cannot fetch body for #{issue_number}"
            )
            return ""
        if isinstance(data, dict):
            return str(data.get("body") or "")
        return ""

    def is_closed(self, issue_number: int) -> bool:
        """Return True if the issue is closed. Conservatively False on error."""
        data = self._github.view_issue(issue_number)
        if not data or data == "network_error":
            logger.bind(domain="orchestra").warning(
                f"Cannot check state of #{issue_number}"
            )
            return False
        if isinstance(data, dict):
            return str(data.get("state", "OPEN")).upper() == "CLOSED"
        return False

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
