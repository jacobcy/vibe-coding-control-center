"""GitHub client review operations."""

import json
import subprocess
from typing import Any

from loguru import logger

from vibe3.clients.github_review_management import ReviewManagementMixin
from vibe3.exceptions import GitHubError, UserError


class ReviewMixin(ReviewManagementMixin):
    """Mixin for review-related operations."""

    def add_pr_comment(self: Any, pr_number: int, body: str) -> None:
        """Add comment to PR."""
        logger.bind(
            external="github", operation="add_comment", pr_number=pr_number
        ).debug("Calling GitHub API: add_pr_comment")
        subprocess.run(
            ["gh", "pr", "comment", str(pr_number), "--body", body],
            check=True,
        )

    def get_pr_diff(self: Any, pr_number: int) -> str:
        """Get PR diff.

        Args:
            pr_number: PR number

        Returns:
            PR diff content

        Raises:
            UserError: If PR has too many files (>300) for GitHub API
            GitHubError: If gh command fails for other reasons
        """
        logger.bind(
            external="github",
            operation="get_diff",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_diff")
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number)],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Failed to get PR diff"
            # Check for GitHub's 300 file limit
            if "diff exceeded the maximum number of files" in error_msg:
                raise UserError(
                    f"PR #{pr_number} has too many files (GitHub limit: 300).\n"
                    f"  Cannot analyze PRs with >300 files via GitHub API.\n"
                    f"  Alternatives:\n"
                    f"    1. Checkout the PR locally and use 'vibe inspect branch'\n"
                    f"    2. View file list at: https://github.com/.../pull/{pr_number}/files"
                ) from e
            raise GitHubError(
                status_code=e.returncode,
                message=error_msg,
            ) from e

    def get_pr_files(self: Any, pr_number: int) -> list[str]:
        """Get list of files changed in PR.

        Args:
            pr_number: PR number

        Returns:
            List of changed file paths

        Raises:
            UserError: If PR has too many files (>300) for GitHub API
            GitHubError: If gh command fails for other reasons
        """
        logger.bind(
            external="github",
            operation="get_pr_files",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_files")
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number), "--name-only"],
                capture_output=True,
                text=True,
                check=True,
            )
            return [f for f in result.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Failed to get PR files"
            # Check for GitHub's 300 file limit
            if "diff exceeded the maximum number of files" in error_msg:
                raise UserError(
                    f"PR #{pr_number} has too many files (GitHub limit: 300).\n"
                    f"  Cannot analyze PRs with >300 files via GitHub API.\n"
                    f"  Alternatives:\n"
                    f"    1. Checkout the PR locally and use 'vibe inspect branch'\n"
                    f"    2. View file list at: https://github.com/.../pull/{pr_number}/files"
                ) from e
            raise GitHubError(
                status_code=e.returncode,
                message=error_msg,
            ) from e

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
