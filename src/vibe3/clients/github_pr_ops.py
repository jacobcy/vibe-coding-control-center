"""GitHub client PR operations."""

import json
import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client_base import raise_gh_pr_error
from vibe3.exceptions import PRNotFoundError
from vibe3.models.pr import CreatePRRequest, PRResponse, PRState, UpdatePRRequest


class PRMixin:
    """Mixin for PR-related operations."""

    # ========================================================================
    # Query Operations (migrated from PRQueryMixin)
    # ========================================================================

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
        ci_status = (
            str(status_rollup).lower() if isinstance(status_rollup, str) else None
        )

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
            ci_status=ci_status,
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
                    ci_status=None,
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

    # ========================================================================
    # Mutation Operations
    # ========================================================================

    def create_pr(self: Any, request: CreatePRRequest) -> PRResponse:
        """Create a pull request."""
        logger.bind(
            external="github",
            operation="create_pr",
            title=request.title,
            head=request.head_branch,
            base=request.base_branch,
            draft=request.draft,
        ).debug("Calling GitHub API: create_pull_request")

        cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            request.title,
            "--body",
            request.body,
            "--base",
            request.base_branch,
            "--head",
            request.head_branch,
        ]

        if request.draft:
            cmd.append("--draft")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(
                e,
                "create",
                user_tips=(
                    f"  1. Ensure branch '{request.head_branch}' is pushed\n"
                    f"  2. Check whether an open PR already exists for this branch"
                ),
            )

        # Parse PR URL from output
        pr_url = result.stdout.strip()
        pr_number = self._extract_pr_number(pr_url)

        # Get the created PR
        pr = self.get_pr(pr_number)
        if pr is None:
            raise PRNotFoundError(pr_number)
        if request.body and not pr.body.strip():
            logger.bind(
                external="github",
                operation="create_pr",
                pr_number=pr_number,
            ).warning("Created PR body is empty; applying fallback body update")
            pr = self.update_pr(
                UpdatePRRequest(
                    number=pr_number,
                    title=None,
                    body=request.body,
                    draft=None,
                    base_branch=None,
                )
            )
        return cast(PRResponse, pr)

    def update_pr(self: Any, request: UpdatePRRequest) -> PRResponse:
        """Update a pull request."""
        logger.bind(
            external="github",
            operation="update_pr",
            number=request.number,
        ).debug("Calling GitHub API: update_pull_request")

        cmd = ["gh", "pr", "edit", str(request.number)]

        if request.title:
            cmd.extend(["--title", request.title])
        if request.body:
            cmd.extend(["--body", request.body])
        if request.base_branch:
            cmd.extend(["--base", request.base_branch])

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(
                e,
                "edit",
                user_tips=(
                    f"  1. Confirm PR #{request.number} exists\n"
                    f"  2. Verify current branch/repo has permission to edit it"
                ),
            )

        # Handle draft status separately
        if request.draft is not None:
            if request.draft:
                try:
                    subprocess.run(
                        ["gh", "pr", "ready", str(request.number), "--undo"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise_gh_pr_error(
                        e,
                        "ready --undo",
                        user_tips=(
                            f"  1. Confirm PR #{request.number} " f"is currently ready"
                        ),
                    )
            else:
                try:
                    subprocess.run(
                        ["gh", "pr", "ready", str(request.number)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise_gh_pr_error(
                        e,
                        "ready",
                        user_tips=(
                            f"  1. Confirm PR #{request.number} is a draft\n"
                            f"  2. Ensure required checks/permissions are satisfied"
                        ),
                    )

        pr = self.get_pr(request.number)
        if pr is None:
            raise PRNotFoundError(request.number)
        return cast(PRResponse, pr)

    def mark_ready(self: Any, pr_number: int) -> PRResponse:
        """Mark PR as ready for review."""
        logger.bind(
            external="github",
            operation="mark_ready",
            pr_number=pr_number,
        ).debug("Calling GitHub API: mark_ready_for_review")

        try:
            subprocess.run(
                ["gh", "pr", "ready", str(pr_number)],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(
                e,
                "ready",
                user_tips=(
                    f"  1. Confirm PR #{pr_number} is a draft\n"
                    f"  2. Ensure required checks/permissions are satisfied"
                ),
            )

        pr = self.get_pr(pr_number)
        if pr is None:
            raise PRNotFoundError(pr_number)
        return cast(PRResponse, pr)

    def merge_pr(self: Any, pr_number: int) -> PRResponse:
        """Merge a pull request."""
        logger.bind(
            external="github",
            operation="merge_pr",
            pr_number=pr_number,
        ).debug("Calling GitHub API: merge_pull_request")

        try:
            subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(
                e,
                "merge",
                user_tips=(
                    f"  1. Confirm PR #{pr_number} is ready and mergeable\n"
                    f"  2. Check required CI/review rules are satisfied"
                ),
            )

        pr = self.get_pr(pr_number)
        if pr is None:
            raise PRNotFoundError(pr_number)
        return cast(PRResponse, pr)

    def close_pr(self: Any, pr_number: int, comment: str | None = None) -> bool:
        """Close a pull request.

        Args:
            pr_number: PR number to close
            comment: Optional comment to add before closing

        Returns:
            True if PR was closed successfully
        """
        logger.bind(
            external="github",
            operation="close_pr",
            pr_number=pr_number,
        ).debug("Calling GitHub API: close_pull_request")

        # Add comment if provided
        if comment:
            try:
                subprocess.run(
                    ["gh", "pr", "comment", str(pr_number), "--body", comment],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                # Log warning but continue with close
                logger.bind(
                    external="github",
                    operation="close_pr",
                    pr_number=pr_number,
                ).warning(f"Failed to add comment before closing: {e.stderr}")

        # Close the PR
        try:
            subprocess.run(
                ["gh", "pr", "close", str(pr_number)],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise_gh_pr_error(
                e,
                "close",
                user_tips=(
                    f"  1. Confirm PR #{pr_number} exists\n"
                    f"  2. Verify current branch/repo has permission to close it"
                ),
            )

        return True
