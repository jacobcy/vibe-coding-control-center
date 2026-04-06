"""GitHub client PR operations."""

import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client_base import raise_gh_pr_error
from vibe3.exceptions import PRNotFoundError
from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest


class PRMixin:
    """Mixin for PR-related operations."""

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
