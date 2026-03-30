"""Protocol definitions for clients."""

from typing import Any, Protocol

from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest  # type: ignore


class GitHubClientProtocol(Protocol):
    """Protocol for GitHub client."""

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        ...

    def create_pr(self, request: CreatePRRequest) -> PRResponse:
        """Create a pull request."""
        ...

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR by number or branch."""
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

    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        ...

    def list_issues(
        self,
        limit: int = 30,
        state: str = "open",
        assignee: str | None = None,
    ) -> list[dict[str, Any]]:
        """List GitHub issues.

        Args:
            limit: Maximum number of issues to fetch
            state: Issue state filter (open, closed, all)
            assignee: Filter by assignee username
        """
        ...

    def view_issue(
        self, issue_number: int, repo: str | None = None
    ) -> "dict[str, Any] | None | str":
        """View a GitHub issue. Returns 'network_error' string on network failure."""
        ...

    def list_prs_for_branch(
        self, branch: str, *, state: str | None = None
    ) -> list[PRResponse]:
        """List PRs for a specific branch."""
        ...
