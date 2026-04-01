"""GitHub client PR query operations."""

import json
import subprocess
from typing import Any

from loguru import logger

from vibe3.models.pr import PRResponse, PRState


class PRQueryMixin:
    """Mixin for PR query operations."""

    def get_pr(
        self: Any, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR by number or branch."""
        logger.bind(
            external="github",
            operation="get_pr",
            pr_number=pr_number,
            branch=branch,
        ).debug("Calling GitHub API: get_pull_request")

        target = str(pr_number) if pr_number else branch
        if not target:
            # Try current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            target = result.stdout.strip()

        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    target,
                    "--json",
                    "number,title,body,state,headRefName,baseRefName,"
                    "url,isDraft,createdAt,updatedAt,mergedAt,mergeable,statusCheckRollup",
                ],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.bind(external="github", target=target).warning(
                "GitHub CLI (gh) not found, skipping PR lookup"
            )
            return None

        if result.returncode != 0:
            logger.bind(external="github", target=target).warning("PR not found")
            return None

        data = json.loads(result.stdout)

        # Determine is_ready: not a draft
        is_ready = not bool(data.get("isDraft", True))

        # Determine ci_passed: check statusCheckRollup
        status_rollup = data.get("statusCheckRollup")
        ci_passed = status_rollup == "SUCCESS" if status_rollup else False

        return PRResponse(
            number=int(data["number"]),
            title=str(data["title"]),
            body=str(data.get("body", "")),
            state=PRState(data["state"]),
            head_branch=str(data["headRefName"]),
            base_branch=str(data["baseRefName"]),
            url=str(data["url"]),
            draft=bool(data.get("isDraft", False)),
            is_ready=is_ready,
            ci_passed=ci_passed,
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            merged_at=data.get("mergedAt"),
            metadata=None,
        )

    def get_pr_commits(self: Any, pr_number: int) -> list[str]:
        """Get list of commit SHAs for a PR."""
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

    def list_prs_for_branch(
        self: Any, branch: str, *, state: str | None = None
    ) -> list[PRResponse]:
        """List PRs for a specific branch."""
        logger.bind(
            external="github",
            operation="list_prs_for_branch",
            branch=branch,
        ).debug("Calling GitHub API: list_prs")

        cmd = [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--json",
            "number,title,state,isDraft,url,headRefName,baseRefName,mergedAt",
        ]
        if state:
            cmd.extend(["--state", state])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

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
                    merged_at=pr_data.get("mergedAt"),
                    metadata=None,
                )
            )

        logger.bind(
            external="github",
            branch=branch,
            pr_count=len(prs),
        ).debug("Retrieved PRs for branch")

        return prs
