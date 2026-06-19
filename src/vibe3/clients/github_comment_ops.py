"""GitHub client comment operations."""

import json
import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client_base import raise_gh_pr_error
from vibe3.exceptions import GitHubError, VibeError


def _generate_ai_review_mention_body(reviewers: list[str]) -> str:
    """Generate mention comment body for AI review requests.

    Format:
    @codex
    @copilot

    Please review changes and fix bugs.
    Focus on code quality, test coverage, and potential issues.
    """
    lines = [f"@{r}" for r in reviewers]
    lines.append("")
    lines.append("Please review changes and fix bugs.")
    lines.append("Focus on code quality, test coverage, and potential issues.")
    return "\n".join(lines)


class CommentMixin:
    """Mixin for GitHub issue/PR comment operations."""

    def list_pr_comments(self: Any, pr_number: int) -> list[dict[str, Any]]:
        """List general comments on a PR."""
        logger.bind(
            external="github",
            operation="list_pr_comments",
            pr_number=pr_number,
        ).debug("Calling GitHub API: list_pr_comments")

        result = self._run_gh_command(
            ["gh", "api", f"repos/:owner/:repo/issues/{pr_number}/comments"]
        )

        if result is None:
            raise GitHubError(
                -1,
                "Failed to list comments: gh command timeout or not found",
            )

        if result.returncode != 0:
            error = subprocess.CalledProcessError(
                result.returncode,
                result.args,
                result.stdout,
                result.stderr,
            )
            raise_gh_pr_error(error, "list comments")

        raw_comments = json.loads(result.stdout)

        # Normalize REST fields to project contract
        normalized = []
        for c in raw_comments:
            c["author"] = c.get("user", {})
            c["createdAt"] = c.get("created_at")
            normalized.append(c)
        return cast(list[dict[str, Any]], normalized)

    def create_pr_comment(self: Any, pr_number: int, body: str) -> str:
        """Create a comment on a PR. Returns comment URL."""
        logger.bind(
            external="github",
            operation="create_pr_comment",
            pr_number=pr_number,
        ).debug("Calling GitHub API: create_pr_comment")

        result = self._run_gh_command(
            ["gh", "pr", "comment", str(pr_number), "--body", body]
        )

        if result is None:
            raise GitHubError(
                -1,
                f"Failed to create comment on PR {pr_number}: "
                "gh command timeout or not found",
            )

        if result.returncode != 0:
            error = subprocess.CalledProcessError(
                result.returncode,
                result.args,
                result.stdout,
                result.stderr,
            )
            raise_gh_pr_error(error, "comment")

        return cast(str, result.stdout.strip())

    def update_pr_comment(self: Any, comment_id: str, body: str) -> str:
        """Update an existing PR comment via GitHub API."""
        logger.bind(
            external="github",
            operation="update_pr_comment",
            comment_id=comment_id,
        ).debug("Calling GitHub API: update_pr_comment")

        result = self._run_gh_command(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/:owner/:repo/issues/comments/{comment_id}",
                "--input",
                "-",
            ],
            input_text=json.dumps({"body": body}),
        )

        if result is None:
            raise GitHubError(
                -1,
                f"Failed to update comment {comment_id}: "
                "gh command timeout or not found",
            )

        if result.returncode != 0:
            error = subprocess.CalledProcessError(
                result.returncode,
                result.args,
                result.stdout,
                result.stderr,
            )
            raise_gh_pr_error(error, f"update comment {comment_id}")

        data = json.loads(result.stdout)
        return cast(str, data.get("html_url", comment_id))

    def request_ai_review(
        self: Any, pr_number: int, reviewers: list[str]
    ) -> str | None:
        """Request AI review by posting mention comment.

        Args:
            pr_number: PR number
            reviewers: List of reviewer names (codex, copilot, claude)

        Returns:
            Comment URL if successful, None if failed
        """
        if not reviewers:
            logger.warning("No reviewers specified, skipping review request")
            return None

        body = _generate_ai_review_mention_body(reviewers)

        try:
            comment_url: str = self.create_pr_comment(pr_number, body)
            logger.info(f"Review request comment posted: {comment_url}")
            return comment_url
        except (VibeError, OSError) as e:
            # VibeError: 项目异常（UserError 或 GitHubError）
            # OSError: 网络/进程相关异常
            logger.error(f"Failed to post review request comment: {e}")
            return None
