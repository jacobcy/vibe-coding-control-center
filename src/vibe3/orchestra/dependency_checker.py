"""Dependency resolution checker for orchestra."""

import json
import re
import subprocess

from loguru import logger

# Patterns to detect "blocked by" in issue body (case-insensitive)
_BLOCKED_BY_PATTERNS = [
    r"blocked\s+by\s+#(\d+)",
    r"depends\s+on\s+#(\d+)",
    r"requires\s+#(\d+)",
    r"blocked-by:\s*#(\d+)",
]


def parse_blocked_by(body: str) -> list[int]:
    """Parse blocking issue numbers from issue body.

    Recognizes patterns like: "blocked by #123", "depends on #123",
    "requires #123", "blocked-by: #123"

    Args:
        body: Issue body text

    Returns:
        List of unique blocking issue numbers (sorted)
    """
    found: set[int] = set()
    lower = body.lower()
    for pattern in _BLOCKED_BY_PATTERNS:
        for match in re.finditer(pattern, lower):
            found.add(int(match.group(1)))
    return sorted(found)


class DependencyChecker:
    """Checks if all blocking issues for a given issue are resolved."""

    def __init__(self, repo: str | None = None):
        self.repo = repo

    def fetch_body(self, issue_number: int) -> str:
        """Fetch issue body from GitHub.

        Returns:
            Issue body text, or empty string on failure
        """
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "body",
        ]
        if self.repo:
            cmd.extend(["--repo", self.repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                logger.bind(domain="orchestra").warning(
                    f"Cannot fetch body for #{issue_number}: {result.stderr.strip()}"
                )
                return ""
            data = json.loads(result.stdout)
            return str(data.get("body") or "")
        except Exception as e:
            logger.bind(domain="orchestra").error(
                f"Failed to fetch body for #{issue_number}: {e}"
            )
            return ""

    def is_closed(self, issue_number: int) -> bool:
        """Return True if the issue is closed.

        Conservatively returns False on any error.
        """
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "state",
        ]
        if self.repo:
            cmd.extend(["--repo", self.repo])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                logger.bind(domain="orchestra").warning(
                    f"Cannot check state of #{issue_number}: {result.stderr.strip()}"
                )
                return False
            data = json.loads(result.stdout)
            return str(data.get("state", "OPEN")).upper() == "CLOSED"
        except Exception as e:
            logger.bind(domain="orchestra").error(
                f"Failed to check #{issue_number}: {e}"
            )
            return False

    def all_resolved(self, blocking_issues: list[int]) -> bool:
        """Return True if every blocking issue is closed.

        Args:
            blocking_issues: List of issue numbers that must be closed

        Returns:
            True only when every issue in the list is closed
        """
        return all(self.is_closed(n) for n in blocking_issues)

    def check(self, issue_number: int) -> tuple[bool, list[int]]:
        """Check whether an issue's dependencies are resolved.

        Fetches the issue body, parses blocking references, and checks
        whether each blocking issue is closed.

        Args:
            issue_number: Issue number to check

        Returns:
            (all_resolved, blocking_numbers) tuple.
            `all_resolved` is True when all blockers are closed.
            `blocking_numbers` is the list of parsed blocking issue numbers.
        """
        body = self.fetch_body(issue_number)
        blockers = parse_blocked_by(body)
        if not blockers:
            return True, []
        resolved = self.all_resolved(blockers)
        return resolved, blockers
