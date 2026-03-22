"""GitHub client issues operations."""

import json
import re
import subprocess
from typing import Any

from loguru import logger

# Patterns GitHub uses to auto-close issues via PR body
_LINKED_ISSUE_RE = re.compile(
    r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#(\d+)",
    re.IGNORECASE,
)


def parse_linked_issues(body: str) -> list[int]:
    """Parse issue numbers from PR body using GitHub closing keywords.

    Recognises: closes/closed/close, fixes/fixed/fix, resolves/resolved/resolve

    Args:
        body: PR body text

    Returns:
        List of issue numbers (deduplicated, order preserved)
    """
    seen: set[int] = set()
    result: list[int] = []
    for m in _LINKED_ISSUE_RE.finditer(body or ""):
        n = int(m.group(1))
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


class IssuesMixin:
    """Mixin for issues-related operations."""

    def list_merged_prs(self: Any, limit: int = 100) -> list[dict[str, Any]]:
        """List merged PRs with branch name and body.

        Args:
            limit: Maximum number of PRs to fetch

        Returns:
            List of dicts with keys: number, headRefName, body, mergedAt
        """
        logger.bind(
            external="github",
            operation="list_merged_prs",
            limit=limit,
        ).debug("Calling GitHub API: list merged PRs")

        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--limit",
                str(limit),
                "--json",
                "number,headRefName,body,mergedAt",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list merged PRs"
            )
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def list_issues(
        self: Any, limit: int = 30, state: str = "open"
    ) -> list[dict[str, Any]]:
        """List GitHub issues."""
        logger.bind(
            external="github",
            operation="list_issues",
            limit=limit,
            state=state,
        ).debug("Calling GitHub API: list_issues")
        cmd = [
            "gh",
            "issue",
            "list",
            "--limit",
            str(limit),
            "--state",
            state,
            "--json",
            "number,title,state,updatedAt,labels",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list issues"
            )
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def view_issue(self: Any, issue_number: int) -> "dict[str, Any] | None | str":
        """View a GitHub issue.

        Returns:
            dict: issue data on success
            None: issue not found or inaccessible
            "network_error": network/auth failure
        """
        logger.bind(
            external="github",
            operation="view_issue",
            issue_number=issue_number,
        ).debug("Calling GitHub API: view_issue")
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,state,updatedAt,labels,comments",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr or ""
            stderr_lower = stderr.lower()
            # 网络/认证错误
            if any(
                kw in stderr_lower
                for kw in (
                    "network",
                    "timeout",
                    "dial",
                    "connection",
                    "unable to connect",
                    "no such host",
                    "authentication",
                    "401",
                    "403",
                )
            ):
                logger.bind(external="github", issue_number=issue_number).warning(
                    f"Network error fetching issue #{issue_number}: {stderr.strip()}"
                )
                return "network_error"
            # issue 不存在
            logger.bind(external="github", issue_number=issue_number).debug(
                f"Issue #{issue_number} not found: {stderr.strip()}"
            )
            return None
        return json.loads(result.stdout)  # type: ignore[no-any-return]
