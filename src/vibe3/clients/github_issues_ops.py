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


_BLOCKED_BY_RE = re.compile(
    r"(?:blocked\s+by|depends\s+on|依赖)[:\s]+([#\d,\s#]+)",
    re.IGNORECASE,
)


def parse_blocked_by(body: str) -> list[int]:
    """Parse issue numbers from 'Blocked by' or 'Depends on' lines in issue body.

    Recognises patterns like:
      Blocked by: #333, #336
      Depends on: #333
      依赖 #338

    Args:
        body: Issue body text

    Returns:
        List of blocking issue numbers (deduplicated, order preserved)
    """
    seen: set[int] = set()
    result: list[int] = []
    for m in _BLOCKED_BY_RE.finditer(body or ""):
        for num in re.findall(r"\d+", m.group(1)):
            n = int(num)
            if n not in seen:
                seen.add(n)
                result.append(n)
    return result


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
            "number,title,body,state,updatedAt,labels,comments,milestone",
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

    def list_issues_with_assignees(
        self: Any,
        limit: int = 100,
        repo: str | None = None,
    ) -> list[dict[str, Any]]:
        """List open issues including assignees and URL fields.

        Used by orchestra to detect assignee changes.

        Args:
            limit: Maximum number of issues to return
            repo: Optional repo override (owner/repo)

        Returns:
            List of dicts with keys: number, title, labels, assignees, url
        """
        logger.bind(
            external="github",
            operation="list_issues_with_assignees",
            limit=limit,
        ).debug("Calling GitHub API: list_issues_with_assignees")

        cmd = [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,labels,assignees,url",
            "--limit",
            str(limit),
        ]
        if repo:
            cmd.extend(["--repo", repo])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list issues with assignees"
            )
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def close_issue(
        self: Any,
        issue_number: int,
        comment: str | None = None,
        repo: str | None = None,
    ) -> bool:
        """Close a GitHub issue, optionally adding a closing comment.

        Args:
            issue_number: Issue number to close
            comment: Optional comment to add when closing
            repo: Optional repo override (owner/repo)

        Returns:
            True if successful, False otherwise
        """
        logger.bind(
            external="github",
            operation="close_issue",
            issue_number=issue_number,
        ).debug("Calling GitHub API: close_issue")

        cmd = ["gh", "issue", "close", str(issue_number)]
        if comment:
            cmd.extend(["--comment", comment])
        if repo:
            cmd.extend(["--repo", repo])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                f"Failed to close issue #{issue_number}"
            )
            return False
        return True

    def add_comment(
        self: Any,
        issue_number: int,
        body: str,
        repo: str | None = None,
    ) -> bool:
        """Add a comment to a GitHub issue.

        Args:
            issue_number: Issue number
            body: Comment body text
            repo: Optional repo override (owner/repo)

        Returns:
            True if successful, False otherwise
        """
        logger.bind(
            external="github",
            operation="add_comment",
            issue_number=issue_number,
        ).debug("Calling GitHub API: add_comment")

        cmd = ["gh", "issue", "comment", str(issue_number), "--body", body]
        if repo:
            cmd.extend(["--repo", repo])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                f"Failed to add comment on #{issue_number}"
            )
            return False
        return True

    def get_pr_for_issue(
        self: Any,
        issue_number: int,
        repo: str | None = None,
    ) -> int | None:
        """Find the PR number that closes a given issue.

        Searches open and closed PRs for closingIssuesReferences.

        Args:
            issue_number: Issue number to look up
            repo: Optional repo override (owner/repo)

        Returns:
            PR number if found, None otherwise
        """
        logger.bind(
            external="github",
            operation="get_pr_for_issue",
            issue_number=issue_number,
        ).debug("Calling GitHub API: get_pr_for_issue")

        cmd = [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--json",
            "number,closingIssuesReferences",
            "--limit",
            "50",
        ]
        if repo:
            cmd.extend(["--repo", repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.bind(external="github", error=result.stderr).error(
                    "Failed to list PRs for issue lookup"
                )
                return None
            prs = json.loads(result.stdout)
            for pr in prs:
                refs = pr.get("closingIssuesReferences", [])
                for ref in refs:
                    if ref.get("number") == issue_number:
                        return int(pr["number"])
        except Exception as exc:
            logger.bind(external="github").error(
                f"Error finding PR for issue #{issue_number}: {exc}"
            )
        return None

    def get_milestone_issues(self: Any, milestone_number: int) -> list[dict[str, Any]]:
        """Get all issues in a milestone (open + closed).

        Args:
            milestone_number: GitHub milestone number

        Returns:
            List of dicts with keys: number, title, state
        """
        logger.bind(
            external="github",
            operation="get_milestone_issues",
            milestone=milestone_number,
        ).debug("Calling GitHub API: get_milestone_issues")
        cmd = [
            "gh",
            "issue",
            "list",
            "--milestone",
            str(milestone_number),
            "--state",
            "all",
            "--limit",
            "50",
            "--json",
            "number,title,state,labels,body",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err = result.stderr.strip()
            logger.bind(external="github", error=result.stderr).warning(
                f"Failed to get milestone {milestone_number} issues: {err}"
            )
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]
