"""GitHub client commit status operations."""

import json
import subprocess
from typing import Any

from loguru import logger

from vibe3.exceptions import GitHubError


class StatusMixin:
    """Mixin for commit status operations."""

    def get_pr_head_sha(self: Any, pr_number: int) -> str:
        """获取 PR 最新 commit 的 SHA.

        Args:
            pr_number: PR 编号

        Returns:
            HEAD commit SHA 字符串

        Raises:
            GitHubError: gh 命令失败
        """
        logger.bind(
            external="github",
            operation="get_pr_head_sha",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_head_sha")

        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", "headRefOid"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise GitHubError(
                status_code=result.returncode, message=result.stderr.strip()
            )

        data = json.loads(result.stdout)
        return str(data["headRefOid"])

    def create_commit_status(
        self: Any,
        sha: str,
        state: str,
        description: str,
        context: str = "vibe-review/risk-score",
    ) -> dict[str, Any]:
        """设置 commit status（用于 Merge Gate）.

        Args:
            sha: commit SHA
            state: "success" | "failure" | "pending" | "error"
            description: 状态描述（最长 140 字符）
            context: status context 标识符

        Returns:
            API 响应 dict

        Raises:
            GitHubError: API 调用失败
        """
        logger.bind(
            external="github",
            operation="create_commit_status",
            sha=sha,
            state=state,
        ).debug("Calling GitHub API: create_commit_status")

        payload = json.dumps(
            {
                "state": state,
                "description": description[:140],
                "context": context,
            }
        )

        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/statuses/{sha}",
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
            logger.bind(
                external="github",
                operation="create_commit_status",
                sha=sha,
                error=result.stderr,
            ).error("Failed to create commit status")
            raise GitHubError(
                status_code=result.returncode, message=result.stderr.strip()
            )

        return json.loads(result.stdout)  # type: ignore[no-any-return]
