"""GitHub client protocols — narrow port protocols for GitHub operations.

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.github import GitHubClientProtocol, PRReadPort

    # Backward compatible (package re-export)
    from vibe3.clients.protocols import GitHubClientProtocol, PRReadPort
"""

from typing import Any, Protocol

# public-api: pending upstream export
from vibe3.models import CreatePRRequest, PRResponse, UpdatePRRequest


class GitHubAuthPort(Protocol):
    """Port for GitHub authentication operations."""

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        ...

    def get_current_user(self) -> str:
        """Get current authenticated user login name."""
        ...


class PRReadPort(Protocol):
    """Port for PR read operations."""

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR by number or branch."""
        ...

    def list_prs_for_branch(
        self, branch: str, *, state: str | None = None, repo: str | None = None
    ) -> list[PRResponse]:
        """List PRs for a specific branch.

        Args:
            branch: Branch name to query
            state: Optional PR state filter
            repo: Optional repository in owner/repo format

        Returns:
            List of PR responses
        """
        ...

    def list_all_prs(
        self, state: str = "open", limit: int = 100, *, repo: str | None = None
    ) -> list[PRResponse]:
        """List all PRs in repository (batch query).

        Batch query optimization: fetch all PRs in one API call
        instead of N calls for N branches.

        Args:
            state: PR state filter (open, closed, merged, all)
            limit: Maximum number of PRs to return
            repo: Optional repository in owner/repo format

        Returns:
            List of PR responses
        """
        ...


class PRWritePort(Protocol):
    """Port for PR write operations."""

    def create_pr(self, request: CreatePRRequest) -> PRResponse:
        """Create a pull request."""
        ...

    def update_pr(self, request: UpdatePRRequest) -> PRResponse:
        """Update a pull request."""
        ...

    def mark_ready(self, pr_number: int) -> PRResponse:
        """Mark PR as ready for review."""
        ...

    def merge_pr(self, pr_number: int) -> PRResponse:
        """Merge a pull request."""
        ...

    def close_pr(self, pr_number: int, comment: str | None = None) -> bool:
        """Close a pull request.

        Args:
            pr_number: PR number to close
            comment: Optional comment to add before closing

        Returns:
            True if PR was closed successfully
        """
        ...


class PRDiffPort(Protocol):
    """Port for PR diff operations."""

    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        ...

    def get_pr_files(self, pr_number: int) -> list[str]:
        """Get list of files changed in PR.

        Args:
            pr_number: PR number

        Returns:
            List of changed file paths
        """
        ...


class PRCommentPort(Protocol):
    """Port for PR comment operations."""

    def list_pr_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List general comments on a PR."""
        ...

    def list_pr_review_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List review (inline) comments on a PR."""
        ...

    def list_pr_reviews(self, pr_number: int) -> list[dict[str, Any]]:
        """List reviews (summary-level reviews) on a PR."""
        ...

    def create_pr_comment(self, pr_number: int, body: str) -> str:
        """Create a comment on a PR. Returns comment URL."""
        ...

    def update_pr_comment(self, comment_id: str, body: str) -> str:
        """Update an existing PR comment. Returns comment URL."""
        ...

    def request_ai_review(self, pr_number: int, reviewers: list[str]) -> str | None:
        """Request AI review by posting mention comment.

        Args:
            pr_number: PR number
            reviewers: List of reviewer names

        Returns:
            Comment URL if successful, None if failed
        """
        ...


class IssueReadPort(Protocol):
    """Port for issue read operations."""

    def view_issue(
        self, issue_number: int, repo: str | None = None
    ) -> "dict[str, Any] | None | str":
        """View a GitHub issue. Returns 'network_error' string on network failure."""
        ...

    def list_issues(
        self,
        limit: int = 30,
        state: str = "open",
        assignee: str | None = None,
        repo: str | None = None,
        label: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """List GitHub issues.

        Args:
            limit: Maximum number of issues to fetch
            state: Issue state filter (open, closed, all)
            assignee: Filter by assignee username
            label: Server-side label filter (reduces payload vs client-side filtering)
            search: Server-side GitHub issue search query
        """
        ...


class IssueWritePort(Protocol):
    """Port for issue write operations."""

    def close_issue(self: Any, issue_number: int, repo: str | None = None) -> bool:
        """Close a GitHub issue.

        Args:
            issue_number: GitHub issue number
            repo: Optional repository in owner/repo format

        Returns:
            True if issue was closed successfully
        """
        ...

    def close_issue_if_open(
        self: Any, issue_number: int, repo: str | None = None
    ) -> bool:
        """Close issue only if it's currently open.

        Args:
            issue_number: GitHub issue number
            repo: Optional repository in owner/repo format

        Returns:
            True if issue was closed or already closed
        """
        ...

    def add_comment(
        self: Any, issue_number: int, body: str, repo: str | None = None
    ) -> str | None:
        """Add a comment to a GitHub issue.

        Args:
            issue_number: GitHub issue number
            body: Comment body
            repo: Optional repository in owner/repo format

        Returns:
            Comment URL if successful, None otherwise
        """
        ...


# Composite protocol for backward compatibility


class GitHubClientProtocol(
    GitHubAuthPort,
    PRReadPort,
    PRWritePort,
    PRDiffPort,
    PRCommentPort,
    IssueReadPort,
    IssueWritePort,
    Protocol,
):
    """Composite protocol for GitHub client combining all narrow ports.

    This protocol maintains backward compatibility with existing code
    that depends on the full GitHub client interface.
    """

    pass


__all__ = [
    "GitHubAuthPort",
    "PRReadPort",
    "PRWritePort",
    "PRDiffPort",
    "PRCommentPort",
    "IssueReadPort",
    "IssueWritePort",
    "GitHubClientProtocol",
]
