"""GitHub client PR query operations."""

import json
import subprocess
from typing import Any

from loguru import logger

from vibe3.models.pr import PRResponse, PRState


class PRQueryMixin:
    """Mixin for PR query operations."""

    def get_pr_commits(self: Any, pr_number: int) -> list[str]:
        """Get list of commit SHAs for a PR.

        Args:
            pr_number: PR number

        Returns:
            List of commit SHA strings

        Raises:
            subprocess.CalledProcessError: If gh command fails
        """
        logger.bind(
            external="github",
            operation="get_pr_commits",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_commits")

        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--json",
                "commits",
                "--jq",
                ".commits[].oid",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse commit SHAs from output
        commits = [
            line.strip() for line in result.stdout.strip().split("\n") if line.strip()
        ]

        logger.bind(
            external="github",
            pr_number=pr_number,
            commit_count=len(commits),
        ).debug("Retrieved PR commits")

        return commits

    def list_prs_for_branch(self: Any, branch: str) -> list[PRResponse]:
        """List PRs for a specific branch.

        Args:
            branch: Branch name to query

        Returns:
            List of PR response objects (empty list if no PRs found)
        """
        logger.bind(
            external="github",
            operation="list_prs_for_branch",
            branch=branch,
        ).debug("Calling GitHub API: list_prs")

        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--json",
                "number,title,state,isDraft,url,headRefName,baseRefName",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse PR list from output
        prs_data = json.loads(result.stdout.strip())
        prs = []
        for pr_data in prs_data:
            prs.append(
                PRResponse(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body="",
                    state=PRState(pr_data["state"].upper()),
                    head_branch=pr_data["headRefName"],
                    base_branch=pr_data["baseRefName"],
                    url=pr_data["url"],
                    draft=pr_data.get("isDraft", False),
                    is_ready=not pr_data.get("isDraft", False),
                    ci_passed=False,
                    created_at=None,
                    updated_at=None,
                    merged_at=None,
                    metadata=None,
                )
            )

        logger.bind(
            external="github",
            branch=branch,
            pr_count=len(prs),
        ).debug("Retrieved PRs for branch")

        return prs
