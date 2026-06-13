"""GitHub client issues operations."""

import difflib
import json
import os
import re
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_field_constants import (
    GITHUB_DEFAULT_LIST_FIELDS,
    GITHUB_DEFAULT_VIEW_FIELDS,
    GITHUB_KNOWN_ISSUE_FIELDS,
)
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

# Pre-computed set for O(1) field validation lookups
_KNOWN_FIELDS_SET: frozenset[str] = frozenset(GITHUB_KNOWN_ISSUE_FIELDS)


def _validate_issue_fields(fields: list[str]) -> None:
    """Validate that all field names are known GitHub issue API fields.

    Raises ValueError with typo suggestions for unknown fields.

    Args:
        fields: List of field names to validate

    Raises:
        ValueError: If any unknown fields are found, with suggestions for typos
    """
    invalid = [f for f in fields if f not in _KNOWN_FIELDS_SET]
    if not invalid:
        return
    suggestions = []
    for f in invalid:
        matches = difflib.get_close_matches(f, _KNOWN_FIELDS_SET, n=1, cutoff=0.6)
        if matches:
            suggestions.append(f"'{f}' (did you mean '{matches[0]}'?)")
        else:
            suggestions.append(f"'{f}'")
    raise ValueError(
        f"Unknown GitHub issue field(s): {', '.join(suggestions)}. "
        f"Known fields: {', '.join(sorted(_KNOWN_FIELDS_SET))}"
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

        result = self._run_gh_command(cmd)
        if result is None or result.returncode != 0:
            if result is not None:
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
        search: str | None = None,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List GitHub issues.

        Args:
            limit: Maximum number of issues to fetch
            state: Issue state filter (open, closed, all)
            assignee: Filter by assignee username
            label: Server-side label filter — passed as ``--label`` to the GitHub
                CLI so GitHub returns only matching issues, reducing both network
                payload and client-side filtering work.
            search: Server-side GitHub issue search query.
            fields: List of fields to fetch. If None, defaults to a set that
                excludes the expensive ``body`` field.
        """
        logger.bind(
            external="github",
            operation="list_issues",
            limit=limit,
            state=state,
            assignee=assignee,
            label=label,
            search=search,
            fields=fields,
        ).debug("Calling GitHub API: list_issues")
        json_fields = (
            ",".join(fields)
            if fields is not None
            else ",".join(GITHUB_DEFAULT_LIST_FIELDS)
        )
        cmd = [
            "gh",
            "issue",
            "list",
            "--limit",
            str(limit),
            "--state",
            state,
            "--json",
            json_fields,
        ]
        if assignee:
            cmd.extend(["--assignee", assignee])
        if label:
            cmd.extend(["--label", label])
        if search:
            cmd.extend(["--search", search])
        if repo:
            cmd.extend(["--repo", repo])
        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    "Failed to list issues"
                )
            return []
        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def batch_get_issues(
        self: Any,
        issue_numbers: list[int],
        repo: str | None = None,
    ) -> dict[int, str] | None:
        """Batch fetch issue titles by issue number.

        This uses the existing issue-list path as a best-effort batch lookup,
        then filters results back to the requested issue numbers because GitHub
        search may also return issues that merely mention those numbers.
        """
        if not issue_numbers:
            return {}

        requested = set(issue_numbers)
        search_terms = " ".join(f"#{n}" for n in issue_numbers)
        try:
            issues = self.list_issues(
                limit=max(len(requested) * 2, 30),
                state="all",
                repo=repo,
                search=search_terms,
                fields=["number", "title"],
            )
        except Exception as e:
            logger.bind(
                external="github",
                operation="batch_get_issues",
                error=str(e),
            ).warning("Unexpected error during batch fetch")
            return None

        titles: dict[int, str] = {}
        for issue in issues:
            num = issue.get("number")
            title = issue.get("title")
            if isinstance(num, int) and num in requested and isinstance(title, str):
                titles[num] = title

        logger.bind(
            external="github",
            operation="batch_get_issues",
            fetched=len(titles),
            requested=len(requested),
        ).debug("Batch fetch completed")
        return titles

    def view_issue(
        self: Any,
        issue_number: int,
        repo: str | None = None,
        fields: list[str] | None = None,
    ) -> "dict[str, Any] | None | str":
        """View a GitHub issue.

        Args:
            issue_number: GitHub issue number.
            repo: Optional ``owner/repo`` string. When provided, passes
                ``--repo`` to ``gh`` so the correct repository is queried
                regardless of the current working directory.
            fields: Optional list of fields to request. If None, uses default
                set excluding comments.

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

        # Validate fields if provided and validation is not skipped
        if fields is not None and not os.environ.get("VIBE_SKIP_FIELD_VALIDATION"):
            _validate_issue_fields(fields)

        fields_str = (
            ",".join(fields)
            if fields is not None
            else ",".join(GITHUB_DEFAULT_VIEW_FIELDS)
        )
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            fields_str,
        ]
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd, pager=True)
        if result is None:
            # Timeout or gh CLI not found
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

    def get_issue_body(
        self: Any, issue_number: int, repo: str | None = None
    ) -> str | None:
        """Get issue body content.

        Args:
            issue_number: Issue number
            repo: Optional repo override (owner/repo)

        Returns:
            Issue body text, or None if not found
        """
        result = self.view_issue(issue_number, repo=repo, fields=["body"])
        if isinstance(result, dict):
            return cast(str | None, result.get("body", ""))
        return None

    def list_issue_comments(
        self, issue_number: int, repo: str | None = None
    ) -> list[dict[str, Any]]:
        """List comments on a GitHub issue.

        Args:
            issue_number: Issue number
            repo: Optional repo override (owner/repo)

        Returns:
            List of comment dicts with keys: id, body, author, etc.
        """
        result = self.view_issue(issue_number, repo=repo, fields=["comments"])
        if isinstance(result, dict):
            return cast(list[dict[str, Any]], result.get("comments", []))
        return []
