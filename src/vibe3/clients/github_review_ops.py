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
    ) -> dict[str, Any]:
        """创建完整 PR review（含行级 comments）.

        Args:
            pr_number: PR 编号
            body: review 总结
            event: APPROVE | REQUEST_CHANGES | COMMENT
            comments: 行级 comment 列表，每项含 path, line, body, side

        Returns:
            API 响应 dict

        Raises:
            GitHubError: API 调用失败
        """
        logger.bind(
            external="github",
            operation="create_review",
            pr_number=pr_number,
            event=event,
            comment_count=len(comments or []),
        ).debug("Calling GitHub API: create_review")

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
