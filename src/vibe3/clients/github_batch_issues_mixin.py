"""GitHub batch issues operations mixin."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    pass


class BatchIssuesMixin:
    """Mixin for batch issue operations."""

    def batch_get_issues(
        self: Any,
        issue_numbers: list[int],
        repo: str | None = None,
    ) -> dict[int, str] | None:
        """Batch fetch multiple issues in a single API call.

        Uses `gh issue list` with JSON output to fetch multiple issues at once.

        Args:
            issue_numbers: List of issue numbers to fetch.
            repo: Optional owner/repo string. If None, uses current repo.

        Returns:
            Dict mapping issue_number -> title on success.
            None on network/auth error.
            Empty dict if no issues found.

        Example:
            >>> client = GitHubClient()
            >>> titles = client.batch_get_issues([123, 456])
            >>> titles[123]
            'Fix the bug in auth.py'
        """
        if not issue_numbers:
            return {}

        logger.bind(
            external="github",
            operation="batch_get_issues",
            count=len(issue_numbers),
        ).debug("Calling GitHub API: batch issue fetch")

        # Use gh issue list with search query to batch fetch
        # Note: gh issue list doesn't support direct number list,
        # so we use search with OR query
        search_terms = " ".join(f"#{n}" for n in issue_numbers)
        cmd = [
            "gh",
            "issue",
            "list",
            "--search",
            search_terms,
            "--json",
            "number,title",
            "--limit",
            str(len(issue_numbers)),
        ]

        if repo:
            cmd.extend(["--repo", repo])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                logger.bind(
                    external="github",
                    operation="batch_get_issues",
                    returncode=result.returncode,
                    stderr=result.stderr,
                ).warning("GitHub API call failed")
                return None

            issues = json.loads(result.stdout)

            # Build mapping: number -> title
            titles: dict[int, str] = {}
            for issue in issues:
                num = issue.get("number")
                title = issue.get("title")
                if num is not None and title is not None:
                    titles[num] = title

            logger.bind(
                external="github",
                operation="batch_get_issues",
                fetched=len(titles),
                requested=len(issue_numbers),
            ).debug("Batch fetch completed")

            return titles

        except subprocess.TimeoutExpired:
            logger.bind(
                external="github",
                operation="batch_get_issues",
            ).warning("GitHub API call timeout")
            return None
        except json.JSONDecodeError as e:
            logger.bind(
                external="github",
                operation="batch_get_issues",
                error=str(e),
            ).warning("Failed to parse GitHub API response")
            return None
        except Exception as e:
            logger.bind(
                external="github",
                operation="batch_get_issues",
                error=str(e),
            ).warning("Unexpected error during batch fetch")
            return None
