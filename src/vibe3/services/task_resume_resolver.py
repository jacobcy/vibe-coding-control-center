"""TaskResumeResolver service - source-aware task resume operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.models.data_source import DataSource
from vibe3.models.resume_state import ResumeState

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow_service import FlowService


SourceStrategy = Literal["local", "remote", "auto"]


class TaskResumeResolver:
    """Resolver for source-aware task resume operations.

    Implements unified source strategy:
    - local: SQLite only, no fallback
    - remote: GitHub API + issue body projection
    - auto: local-first, remote fallback when SQLite missing
    """

    def __init__(
        self,
        store: SQLiteClient,
        flow_service: FlowService | None = None,
    ) -> None:
        """Initialize resolver with SQLite client.

        Args:
            store: SQLiteClient for database operations
            flow_service: Optional FlowService instance
        """
        self.store = store
        self.flow_service = flow_service

    def resolve_resume_state(
        self,
        issue_number: int,
        source: Literal["local", "remote", "auto"],
    ) -> ResumeState:
        """Resolve resume state with source strategy.

        Args:
            issue_number: Issue number to resume
            source: "local" | "remote" | "auto"

        Returns:
            ResumeState with source metadata

        Raises:
            UserError: If local source and flow not found
            SystemError: If remote source and GitHub API fails
        """
        if source == "local":
            return self._read_local(issue_number)

        if source == "remote":
            return self._read_remote(issue_number)

        # auto: local-first with remote fallback
        try:
            return self._read_local(issue_number)
        except Exception:
            logger.bind(
                domain="resolver",
                action="resolve_resume_state",
                issue_number=issue_number,
            ).warning("Local read failed, falling back to remote")
            return self._read_remote(issue_number)

    def _read_local(self, issue_number: int) -> ResumeState:
        """Read from local SQLite only."""
        from vibe3.exceptions import UserError

        # Resolve branch from issue number
        branch = self._resolve_branch_from_issue(issue_number)
        if not branch:
            raise UserError(f"No flow found for issue #{issue_number}")

        # Get flow status from SQLite
        if not self.flow_service:
            raise UserError("FlowService not initialized")

        response = self.flow_service.get_flow_status(branch)
        if response is None:
            raise UserError(f"Flow not found for issue #{issue_number}")

        return ResumeState(
            issue_number=issue_number,
            branch=branch,
            blocked_by_issue=response.blocked_by_issue,
            blocked_reason=response.blocked_reason,
            data_source=DataSource.LOCAL_SQLITE,
        )

    def _read_remote(self, issue_number: int) -> ResumeState:
        """Read from GitHub API + issue body projection."""
        from vibe3.clients.github_client import GitHubClient
        from vibe3.exceptions import SystemError
        from vibe3.services.issue_body_service import parse_projection_with_fallback

        github_client = GitHubClient()

        logger.bind(
            domain="resolver",
            action="resolve_remote",
            issue_number=issue_number,
        ).debug("Reading resume state from GitHub")

        # Fetch issue data
        issue = github_client.view_issue(issue_number)
        if not issue or issue == "network_error":
            raise SystemError(f"Failed to fetch issue #{issue_number}")

        # Type guard: issue is dict at this point
        assert isinstance(issue, dict)

        # Parse projection from issue body
        body = issue.get("body", "")
        projection = parse_projection_with_fallback(body) if body else None

        # Extract state from issue
        assignee = (
            issue.get("assignee", {}).get("login") if issue.get("assignee") else None
        )
        labels = [label["name"] for label in issue.get("labels", [])]

        # Determine branch from issue number (canonical pattern)
        branch = f"task/issue-{issue_number}"

        return ResumeState(
            issue_number=issue_number,
            branch=branch,
            blocked_by_issue=(
                projection.blocked_by[0]
                if projection and projection.blocked_by
                else None
            ),
            blocked_reason=projection.blocked_reason if projection else None,
            assignee=assignee,
            labels=labels,
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )

    def _resolve_branch_from_issue(self, issue_number: int) -> str | None:
        """Resolve branch name from issue number."""
        # Use existing method to get flow by issue
        flows = self.store.get_flows_by_issue(issue_number, role="task")
        if flows:
            return flows[0].get("branch")
        return None
