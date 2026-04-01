"""GitHub client comment operations."""

import json
import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client_base import raise_gh_pr_error


class CommentMixin:
    """Mixin for GitHub issue/PR comment operations."""

    def list_pr_comments(self: Any, pr_number: int) -> list[dict[str, Any]]:
        """List general comments on a PR."""
        logger.bind(
            external="github",
            operation="list_pr_comments",
            pr_number=pr_number,
        ).debug("Calling GitHub API: list_pr_comments")

        try:
            repo_result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo = json.loads(repo_result.stdout)["nameWithOwner"]

            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{repo}/issues/{pr_number}/comments",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            raw_comments = json.loads(result.stdout)

            # Normalize REST fields to project contract
            normalized = []
            for c in raw_comments:
                c["author"] = c.get("user", {})
                c["createdAt"] = c.get("created_at")
                normalized.append(c)
            return cast(list[dict[str, Any]], normalized)
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(e, "list comments")

    def create_pr_comment(self: Any, pr_number: int, body: str) -> str:
        """Create a comment on a PR. Returns comment URL."""
        logger.bind(
            external="github",
            operation="create_pr_comment",
            pr_number=pr_number,
        ).debug("Calling GitHub API: create_pr_comment")

        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr_number),
                    "--body",
                    body,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(e, "comment")

    def update_pr_comment(self: Any, comment_id: str, body: str) -> str:
        """Update an existing PR comment via GitHub API."""
        logger.bind(
            external="github",
            operation="update_pr_comment",
            comment_id=comment_id,
        ).debug("Calling GitHub API: update_pr_comment")

        try:
            repo_result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo = json.loads(repo_result.stdout)["nameWithOwner"]

            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/comments/{comment_id}",
                    "--input",
                    "-",
                ],
                input=json.dumps({"body": body}),
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            return cast(str, data.get("html_url", comment_id))
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(e, f"update comment {comment_id}")
