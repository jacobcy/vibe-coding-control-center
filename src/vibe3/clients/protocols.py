"""Protocol definitions for clients."""

from typing import Any, Protocol

from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest  # type: ignore


class BackendProtocol(Protocol):
    """Protocol for backend operations (tmux, execution).

    Used for dependency injection to avoid architecture layer violations.
    Services layer depends on this protocol, concrete implementation
    (CodeagentBackend) is injected at handler/orchestration layer.
    """

    def has_tmux_session(self, session_name: str) -> bool:
        """Check if tmux session exists.

        Args:
            session_name: Exact tmux session name to check

        Returns:
            True if session exists, False otherwise
        """
        ...

    def list_tmux_sessions(self, *, prefix: str | None = None) -> set[str]:
        """List tmux sessions, optionally filtered by prefix.

        Args:
            prefix: Optional prefix to filter sessions (e.g., "vibe3-manager")

        Returns:
            Set of tmux session names
        """
        ...


class GitHubClientProtocol(Protocol):
    """Protocol for GitHub client."""

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        ...

    def get_current_user(self) -> str:
        """Get current authenticated user login name."""
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

    def close_pr(self, pr_number: int, comment: str | None = None) -> bool:
        """Close a pull request.

        Args:
            pr_number: PR number to close
            comment: Optional comment to add before closing

        Returns:
            True if PR was closed successfully
        """
        ...

    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff."""
        ...

    def list_issues(
        self,
        limit: int = 30,
        state: str = "open",
        assignee: str | None = None,
        repo: str | None = None,
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

    def list_pr_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List general comments on a PR."""
        ...

    def list_pr_review_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """List review (inline) comments on a PR."""
        ...

    def create_pr_comment(self, pr_number: int, body: str) -> str:
        """Create a comment on a PR. Returns comment URL."""
        ...

    def update_pr_comment(self, comment_id: str, body: str) -> str:
        """Update an existing PR comment. Returns comment URL."""
        ...
