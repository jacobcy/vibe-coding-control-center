"""GitHub client issues operations."""

import json
import subprocess
from typing import Any

from loguru import logger


class IssuesMixin:
    """Mixin for issues-related operations."""

    def list_issues(
        self: Any, limit: int = 30, state: str = "open"
    ) -> list[dict[str, Any]]:
        """List GitHub issues."""
        logger.bind(
            external="github",
            operation="list_issues",
            limit=limit,
            state=state,
        ).debug("Calling GitHub API: list_issues")
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
            logger.bind(external="github", error=result.stderr).error(
                "Failed to list issues"
            )
            return []
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def view_issue(self: Any, issue_number: int) -> dict[str, Any] | None:
        """View a GitHub issue."""
        logger.bind(
            external="github",
            operation="view_issue",
            issue_number=issue_number,
        ).debug("Calling GitHub API: view_issue")
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
            logger.bind(external="github", error=result.stderr).error(
                "Failed to view issue"
            )
            return None
        return json.loads(result.stdout)  # type: ignore[no-any-return]
