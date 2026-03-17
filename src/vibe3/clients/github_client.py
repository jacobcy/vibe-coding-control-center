"""GitHub client implementation."""

import json
import subprocess
from typing import Any

from loguru import logger

from vibe3.exceptions import PRNotFoundError
from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest


class GitHubClient:
    """GitHub client for interacting with GitHub via gh CLI."""

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("Failed to check auth", error=str(e))
            return False

    def create_pr(self, request: CreatePRRequest) -> PRResponse:
        """Create a pull request."""
        logger.info(
            "Creating PR",
            title=request.title,
            head=request.head_branch,
            base=request.base_branch,
            draft=request.draft,
        )

        cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            request.title,
            "--body",
            request.body,
            "--base",
            request.base_branch,
            "--head",
            request.head_branch,
        ]

        if request.draft:
            cmd.append("--draft")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse PR URL from output
        pr_url = result.stdout.strip()
        pr_number = self._extract_pr_number(pr_url)

        # Get the created PR
        pr = self.get_pr(pr_number)
        if not pr:
            raise PRNotFoundError(pr_number)
        return pr

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR by number or branch."""
        logger.debug("Getting PR", pr_number=pr_number, branch=branch)

        target = str(pr_number) if pr_number else branch
        if not target:
            # Try current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            target = result.stdout.strip()

        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                target,
                "--json",
                "number,title,body,state,headRefName,baseRefName,"
                "url,isDraft,createdAt,updatedAt,mergedAt",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning("PR not found", target=target)
            return None

        data = json.loads(result.stdout)
        return PRResponse(
            number=data["number"],
            title=data["title"],
            body=data.get("body", ""),
            state=data["state"],
            head_branch=data["headRefName"],
            base_branch=data["baseRefName"],
            url=data["url"],
            draft=data.get("isDraft", False),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            merged_at=data.get("mergedAt"),
            metadata=None,
        )

    def update_pr(self, request: UpdatePRRequest) -> PRResponse:
        """Update a pull request."""
        logger.info("Updating PR", number=request.number)

        cmd = ["gh", "pr", "edit", str(request.number)]

        if request.title:
            cmd.extend(["--title", request.title])
        if request.body:
            cmd.extend(["--body", request.body])
        if request.base_branch:
            cmd.extend(["--base", request.base_branch])

        subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Handle draft status separately
        if request.draft is not None:
            if request.draft:
                subprocess.run(
                    ["gh", "pr", "ready", str(request.number), "--undo"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                subprocess.run(
                    ["gh", "pr", "ready", str(request.number)],
                    capture_output=True,
                    text=True,
                    check=True,
                )

        pr = self.get_pr(request.number)
        if not pr:
            raise PRNotFoundError(request.number)
        return pr

    def mark_ready(self, pr_number: int) -> PRResponse:
        """Mark PR as ready for review."""
        logger.info("Marking PR as ready", pr_number=pr_number)

        subprocess.run(
            ["gh", "pr", "ready", str(pr_number)],
            capture_output=True,
            text=True,
            check=True,
        )

        pr = self.get_pr(pr_number)
        if not pr:
            raise PRNotFoundError(pr_number)
        return pr

    def merge_pr(self, pr_number: int) -> PRResponse:
        """Merge a pull request."""
        logger.info("Merging PR", pr_number=pr_number)

        subprocess.run(
            ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
            capture_output=True,
            text=True,
            check=True,
        )

        pr = self.get_pr(pr_number)
        if not pr:
            raise PRNotFoundError(pr_number)
        return pr

    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from URL."""
        # Extract from URL like https://github.com/owner/repo/pull/123
        return int(pr_url.rstrip("/").split("/")[-1])

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        """Add comment to PR."""
        logger.info("Adding comment to PR", pr_number=pr_number)
        subprocess.run(
            ["gh", "pr", "comment", str(pr_number), "--body", body],
            check=True,
        )

    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        logger.info("Getting PR diff", pr_number=pr_number)
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def list_issues(self, limit: int = 30, state: str = "open") -> list[dict[str, Any]]:
        """List GitHub issues."""
        logger.debug("Listing issues", limit=limit, state=state)
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
            logger.error("Failed to list issues", error=result.stderr)
            return []
        return json.loads(result.stdout)  # type: ignore

    def view_issue(self, issue_number: int) -> dict[str, Any] | None:
        """View a GitHub issue."""
        logger.debug("Viewing issue", issue_number=issue_number)
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
            logger.error("Failed to view issue", error=result.stderr)
            return None
        return json.loads(result.stdout)  # type: ignore
