"""GitHub issue body operations mixin."""

from __future__ import annotations

import json
import subprocess
from typing import Any, cast

from loguru import logger

GH_API_TIMEOUT = 30


class IssueBodyMixin:
    """Mixin for reading and writing GitHub issue body."""

    def get_issue_body(self: Any, issue_number: int) -> str | None:
        """Get issue body content.

        Args:
            issue_number: Issue number

        Returns:
            Issue body text, or None if not found
        """
        logger.bind(
            external="github",
            operation="get_issue_body",
            issue_number=issue_number,
        ).debug("Calling GitHub API: issue view")

        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "body",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=GH_API_TIMEOUT
            )
            if result.returncode != 0:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to get issue #{issue_number} body"
                )
                return None

            data = json.loads(result.stdout)
            return cast(str | None, data.get("body", ""))
        except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            logger.bind(
                external="github",
                operation="get_issue_body",
                issue_number=issue_number,
                error=str(e),
            ).warning(f"Transient error reading issue body: {e}")
            return None

    def update_issue_body(
        self: Any,
        issue_number: int,
        body: str,
    ) -> bool:
        """Update issue body content.

        Args:
            issue_number: Issue number
            body: New body content

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

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=GH_API_TIMEOUT
            )
            if result.returncode != 0:
                logger.bind(external="github", error=result.stderr).error(
                    f"Failed to update issue #{issue_number} body"
                )
                return False
            return True
        except subprocess.TimeoutExpired as e:
            logger.bind(
                external="github",
                operation="update_issue_body",
                issue_number=issue_number,
                error=str(e),
            ).warning(f"Timeout updating issue body: {e}")
            return False
