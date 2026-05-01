"""GitHub client issues operations."""

import json
import os
import re
import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_issue_admin_ops import IssueAdminMixin

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


class IssuesMixin(IssueAdminMixin):
    """Mixin for issues-related operations."""

    def list_merged_prs(self: Any, limit: int | None = 100) -> list[dict[str, Any]]:
        """List merged PRs with branch name and body.

        Args:
            limit: Maximum number of PRs to fetch. If None, fetch up to 5000 results.

        Returns:
            List of dicts with keys: number, headRefName, body, mergedAt
        """
        logger.bind(
            external="github",
            operation="list_merged_prs",
            limit=limit,
        ).debug("Calling GitHub API: list merged PRs")

        # Use large explicit limit for "fetch all" case instead of omitting flag
        # (gh defaults to 30 when --limit is absent, does NOT auto-paginate)
        effective_limit = limit if limit is not None else 5000

        cmd = [
            "gh",
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(effective_limit),
            "--json",
            "number,headRefName,body,mergedAt",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list merged PRs"
            )
            return []
        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def list_issues(
        self,
        limit: int = 30,
        state: str = "open",
        assignee: str | None = None,
        repo: str | None = None,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """List GitHub issues.

        Args:
            limit: Maximum number of issues to fetch
            state: Issue state filter (open, closed, all)
            assignee: Filter by assignee username
            label: Server-side label filter — passed as ``--label`` to the GitHub
                CLI so GitHub returns only matching issues, reducing both network
                payload and client-side filtering work.
        """
        logger.bind(
            external="github",
            operation="list_issues",
            limit=limit,
            state=state,
            assignee=assignee,
            label=label,
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
            "number,title,body,state,updatedAt,labels,assignees,milestone",
        ]
        if assignee:
            cmd.extend(["--assignee", assignee])
        if label:
            cmd.extend(["--label", label])
        if repo:
            cmd.extend(["--repo", repo])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list issues"
            )
            return []
        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def view_issue(
        self: Any, issue_number: int, repo: str | None = None
    ) -> "dict[str, Any] | None | str":
        """View a GitHub issue.

        Args:
            issue_number: GitHub issue number.
            repo: Optional ``owner/repo`` string. When provided, passes
                ``--repo`` to ``gh`` so the correct repository is queried
                regardless of the current working directory.

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
            "number,title,body,state,updatedAt,labels,comments,milestone,assignees",
        ]
        if repo:
            cmd.extend(["--repo", repo])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, "GH_PAGER": "cat"},
            )
        except subprocess.TimeoutExpired:
            logger.bind(external="github", issue_number=issue_number).warning(
                f"Timed out fetching issue #{issue_number}"
            )
            return "network_error"
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
        return cast("dict[str, Any] | None | str", json.loads(result.stdout))

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
        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def search_issues(
        self,
        query: str,
        limit: int = 30,
        state: str = "open",
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search GitHub issues using gh issue list --search.

        Args:
            query: Search query string
            limit: Maximum number of results
            state: Issue state filter (open, closed, all)
            label: Optional label filter

        Returns:
            List of issue dicts with number, title, state, labels
        """
        logger.bind(
            external="github",
            operation="search_issues",
            query=query,
            limit=limit,
            state=state,
            label=label,
        ).debug("Calling GitHub API: search_issues")
        cmd = [
            "gh",
            "issue",
            "list",
            "--search",
            query,
            "--limit",
            str(limit),
            "--state",
            state,
            "--json",
            "number,title,state,labels",
        ]
        if label:
            cmd.extend(["--label", label])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).error(
                "Failed to search issues"
            )
            return []
        return cast(list[dict[str, Any]], json.loads(result.stdout))
