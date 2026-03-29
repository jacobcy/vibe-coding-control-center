"""GitHub issue admin operations mixin."""

import json
import subprocess
from typing import Any

from loguru import logger


class IssueAdminMixin:
    """Mixin for advanced issue operations used by orchestra."""

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
