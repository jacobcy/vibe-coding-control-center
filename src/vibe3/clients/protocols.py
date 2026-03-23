"""Protocol definitions for clients."""

from typing import Any, Protocol

from vibe3.models.pr import CreatePRRequest, PRResponse, UpdatePRRequest  # type: ignore


class StoreClientProtocol(Protocol):
    """Protocol for SQLite store client."""

    def get_flow_state(self, branch: str) -> dict[str, Any] | None:
        """Get flow state by branch."""
        ...

    def update_flow_state(self, branch: str, **kwargs: Any) -> None:
        """Update flow state for branch."""
        ...

    def add_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str | None = None,
        refs: dict[str, Any] | None = None,
    ) -> None:
        """Add event to flow."""
        ...

    def get_events(
        self,
        branch: str,
        event_type: str | None = None,
        event_type_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get events for branch."""
        ...

    def add_issue_link(self, branch: str, issue_number: int, role: str) -> None:
        """Add issue link to flow."""
        ...

    def get_issue_links(self, branch: str) -> list[dict[str, Any]]:
        """Get issue links for branch."""
        ...

    def get_active_flows(self) -> list[dict[str, Any]]:
        """Get all active flows."""
        ...

    def get_all_flows(self) -> list[dict[str, Any]]:
        """Get all flows."""
        ...


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

    def list_issues(self, limit: int = 30, state: str = "open") -> list[dict[str, Any]]:
        """List GitHub issues."""
        ...

    def view_issue(self, issue_number: int) -> "dict[str, Any] | None | str":
        """View a GitHub issue. Returns 'network_error' string on network failure."""
        ...

    def list_prs_for_branch(self, branch: str) -> list[PRResponse]:
        """List PRs for a specific branch."""
        ...
