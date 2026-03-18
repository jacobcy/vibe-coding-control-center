"""GitHub client review operations."""

import json
import subprocess
from typing import Any

from loguru import logger


class ReviewMixin:
    """Mixin for review-related operations."""

    def add_pr_comment(self: Any, pr_number: int, body: str) -> None:
        """Add comment to PR."""
        logger.bind(
            external="github",
            operation="add_comment",
            pr_number=pr_number,
        ).debug("Calling GitHub API: add_pr_comment")
        subprocess.run(
            ["gh", "pr", "comment", str(pr_number), "--body", body],
            check=True,
        )

    def get_pr_diff(self: Any, pr_number: int) -> str:
        """Get PR diff."""
        logger.bind(
            external="github",
            operation="get_diff",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_diff")
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def list_reviews(self: Any, pr_number: int) -> list[dict[str, Any]]:
        """List all reviews on a PR.

        Args:
            pr_number: PR 编号

        Returns:
            List of review dicts
        """
        logger.bind(
            external="github",
            operation="list_reviews",
            pr_number=pr_number,
        ).debug("Calling GitHub API: list_reviews")

        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def dismiss_review(self: Any, pr_number: int, review_id: int, message: str) -> None:
        """Dismiss a review.

        Args:
            pr_number: PR 编号
            review_id: Review ID
            message: Dismissal message
        """
        logger.bind(
            external="github",
            operation="dismiss_review",
            pr_number=pr_number,
            review_id=review_id,
        ).debug("Calling GitHub API: dismiss_review")

        subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews/{review_id}/dismissals",
                "--method",
                "PUT",
                "--field",
                f"message={message}",
            ],
            check=True,
        )

    def dismiss_bot_reviews(
        self: Any, pr_number: int, bot_name: str = "github-actions[bot]"
    ) -> None:
        """Dismiss all pending reviews from a bot.

        Args:
            pr_number: PR 编号
            bot_name: Bot user name to filter
        """
        log = logger.bind(
            external="github",
            operation="dismiss_bot_reviews",
            pr_number=pr_number,
            bot_name=bot_name,
        )
        log.debug("Checking for existing bot reviews")

        reviews = self.list_reviews(pr_number)
        bot_reviews = [
            r
            for r in reviews
            if r.get("user", {}).get("login") == bot_name
            and r.get("state") == "PENDING"
        ]

        if bot_reviews:
            log.bind(count=len(bot_reviews)).info("Dismissing existing bot reviews")
            for review in bot_reviews:
                self.dismiss_review(
                    pr_number,
                    review["id"],
                    "Dismissing outdated review - new review in progress",
                )
        else:
            log.debug("No pending bot reviews found")

    def post_review_comment(
        self: Any,
        pr_number: int,
        path: str,
        line: int,
        body: str,
        side: str = "RIGHT",
    ) -> dict[str, Any]:
        """发送行级 review comment.

        Args:
            pr_number: PR 编号
            path: 文件路径
            line: 行号
            body: 评论内容
            side: "RIGHT"（新代码）或 "LEFT"（旧代码）

        Returns:
            API 响应 dict
        """
        logger.bind(
            external="github",
            operation="post_review_comment",
            pr_number=pr_number,
            path=path,
            line=line,
        ).debug("Calling GitHub API: post_review_comment")

        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
                "--method",
                "POST",
                "--field",
                f"path={path}",
                "--field",
                f"line={line}",
                "--field",
                f"body={body}",
                "--field",
                f"side={side}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def create_review(
        self: Any,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: list[dict[str, Any]] | None = None,
        dismiss_previous: bool = False,
    ) -> dict[str, Any]:
        """创建完整 PR review（含行级 comments）.

        Args:
            pr_number: PR 编号
            body: review 总结
            event: APPROVE | REQUEST_CHANGES | COMMENT
            comments: 行级 comment 列表，每项含 path, line, body, side
            dismiss_previous: 是否先dismiss之前的bot reviews

        Returns:
            API 响应 dict

        Raises:
            GitHubError: API 调用失败
        """
        log = logger.bind(
            external="github",
            operation="create_review",
            pr_number=pr_number,
            event=event,
            comment_count=len(comments or []),
        )
        log.debug("Calling GitHub API: create_review")

        # 先 dismiss 之前的 bot reviews（避免重复）
        if dismiss_previous:
            self.dismiss_bot_reviews(pr_number)

        payload = json.dumps(
            {
                "body": body,
                "event": event,
                "comments": comments or [],
            }
        )

        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            input=payload,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            from vibe3.exceptions import GitHubError

            raise GitHubError(
                status_code=result.returncode, message=result.stderr.strip()
            )

        return json.loads(result.stdout)  # type: ignore[no-any-return]
