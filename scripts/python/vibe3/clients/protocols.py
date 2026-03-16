"""Protocol definitions for clients."""

from typing import Protocol

from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest


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

    def add_pr_comment(self, pr_number: int, body: str) -> None:
        """Add comment to PR."""
        ...

    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        ...
