"""GitHub issue admin operations mixin."""

from __future__ import annotations

import json
from typing import Any, cast

from loguru import logger


class IssueAdminMixin:
    """Mixin for advanced issue operations used by orchestra."""

    def remove_assignees(
        self,
        issue_number: int,
        assignees: list[str],
        repo: str | None = None,
    ) -> bool:
        """Remove one or more assignees from a GitHub issue."""
        normalized = [assignee.strip() for assignee in assignees if assignee.strip()]
        if not normalized:
            return True

        logger.bind(
            external="github",
            operation="remove_assignees",
            issue_number=issue_number,
            assignee_count=len(normalized),
        ).debug("Calling GitHub API: remove_assignees")

        cmd = ["gh", "issue", "edit", str(issue_number)]
        for assignee in normalized:
            cmd.extend(["--remove-assignee", assignee])
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to remove assignees from issue #{issue_number}"
                )
            return False
        return True

    def add_assignee(
        self,
        issue_number: int,
        assignee: str,
        repo: str | None = None,
    ) -> bool:
        """Add an assignee to a GitHub issue.

        Args:
            issue_number: Issue number
            assignee: GitHub username to assign
            repo: Optional repo override (owner/repo)

        Returns:
            True if successful, False otherwise
        """
        logger.bind(
            external="github",
            operation="add_assignee",
            issue_number=issue_number,
            assignee=assignee,
        ).debug("Calling GitHub API: add_assignee")

        cmd = ["gh", "issue", "edit", str(issue_number), "--add-assignee", assignee]
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to add assignee to issue #{issue_number}"
                )
            return False
        return True

    def list_issues_with_assignees(
        self,
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

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    "Failed to list issues with assignees"
                )
            return []
        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def close_issue(
        self,
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

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to close issue #{issue_number}"
                )
            return False
        return True

    def add_comment(
        self,
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

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to add comment on #{issue_number}"
                )
            return False
        return True

    def close_issue_if_open(
        self,
        issue_number: int,
        closing_comment: str | None = None,
        repo: str | None = None,
    ) -> str:
        """Close a GitHub issue with pre-check for already-closed state.

        Handles the "already closed" case gracefully to support
        abandonment flows where the issue may already be closed.

        Args:
            issue_number: Issue number to close
            closing_comment: Optional comment explaining why
            repo: Optional repo override (owner/repo)

        Returns:
            Result string: "closed", "already_closed", or "failed"
        """
        logger.bind(
            external="github",
            operation="close_issue_if_open",
            issue_number=issue_number,
        ).debug("Closing issue with pre-check")

        # Check if already closed (avoid unnecessary API call)
        try:
            issue_payload = self.view_issue(issue_number, repo=repo)  # type: ignore[attr-defined]
        except (FileNotFoundError, OSError, RuntimeError) as exc:
            logger.bind(
                external="github",
                issue_number=issue_number,
                error=str(exc),
            ).warning(
                "Failed to fetch issue payload before close, "
                "proceeding with close operation"
            )
            issue_payload = None

        if isinstance(issue_payload, dict) and issue_payload.get("state") == "closed":
            logger.bind(
                external="github",
                issue_number=issue_number,
            ).debug("Issue already closed")
            return "already_closed"

        success = self.close_issue(
            issue_number=issue_number,
            comment=closing_comment,
            repo=repo,
        )

        if success:
            logger.bind(
                external="github",
                issue_number=issue_number,
            ).debug("Issue closed successfully")
            return "closed"
        else:
            logger.bind(
                external="github",
                issue_number=issue_number,
            ).error("Failed to close issue")
            return "failed"

    def create_issue(
        self,
        *,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
        repo: str | None = None,
    ) -> int | None:
        """Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue body/description
            labels: Optional list of labels to apply
            assignees: Optional list of assignees (GitHub usernames)
            repo: Optional repo override (owner/repo)

        Returns:
            Created issue number, or None on failure
        """
        logger.bind(
            external="github",
            operation="create_issue",
            title=title,
        ).debug("Calling GitHub API: create_issue")

        cmd = ["gh", "issue", "create", "--title", title, "--body", body]

        if labels:
            for label in labels:
                cmd.extend(["--label", label])

        if assignees:
            for assignee in assignees:
                cmd.extend(["--assignee", assignee])

        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]

        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to create issue: {title}"
                )
            return None

        # Parse issue number from URL
        # Output format: https://github.com/owner/repo/issues/42
        try:
            issue_url = result.stdout.strip()
            issue_number = int(issue_url.rstrip("/").split("/")[-1])
            logger.bind(
                external="github",
                issue_number=issue_number,
            ).debug("Issue created successfully")
            return issue_number
        except (ValueError, IndexError) as exc:
            logger.bind(
                external="github",
                output=result.stdout,
                error=str(exc),
            ).error("Failed to parse issue number from create output")
            return None

    def update_issue_body(
        self: Any, issue_number: int, body: str, repo: str | None = None
    ) -> bool:
        """Update issue body content.

        Args:
            issue_number: Issue number
            body: New body content
            repo: Optional repo override (owner/repo)

        Returns:
            True if successful, False otherwise
        """
        logger.bind(
            external="github",
            operation="update_issue_body",
            issue_number=issue_number,
            body_length=len(body),
        ).debug("Calling GitHub API: issue edit")

        cmd = [
            "gh",
            "issue",
            "edit",
            str(issue_number),
            "--body",
            body,
        ]
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)  # type: ignore[attr-defined]
        if result is None or result.returncode != 0:
            if result is not None:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to update issue #{issue_number} body"
                )
            return False
        return True
