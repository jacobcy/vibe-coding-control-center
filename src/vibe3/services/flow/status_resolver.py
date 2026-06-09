"""FlowStatusResolver service - source-aware flow status reads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models import DataSource, FlowStatusResponse
from vibe3.services.flow.service import FlowService
from vibe3.services.issue.body import parse_projection
from vibe3.utils import compute_blocked_reason_summary

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class FlowStatusResolver:
    """Resolver for source-aware flow status reads.

    Implements source strategy:
    - Default (remote=False): Local-first with remote fallback when SQLite missing
    - Remote mode (remote=True): Fetch complete state from GitHub issue + comments
    """

    def __init__(
        self,
        store: SQLiteClient,
        flow_service: FlowService | None = None,
    ) -> None:
        """Initialize resolver with SQLite client.

        Args:
            store: SQLiteClient for database operations
            flow_service: Optional FlowService instance (defaults to creating one)
        """
        self.store = store
        self.flow_service = flow_service or FlowService(store=store)

    def resolve(
        self,
        branch: str,
        remote: bool = False,
        issue_number: int | None = None,
    ) -> FlowStatusResponse | None:
        """Resolve flow status with source strategy.

        Args:
            branch: Branch name to query
            remote: If True, fetch complete remote state from GitHub
            issue_number: Task issue number (required if remote=True)

        Returns:
            FlowStatusResponse with data_source field set,
            or None if not found

        Raises:
            ValueError: If remote=True but no issue_number
        """
        if remote:
            if not issue_number:
                from vibe3.exceptions import UserError

                raise UserError(
                    "Cannot use --remote without issue number. "
                    "Bind a task issue first: vibe3 flow bind <issue> --role task"
                )
            return self._read_remote(branch, issue_number)

        # Default: local-first with remote fallback
        result = self._read_local(branch)
        if result is not None:
            return result

        # Local not found, try fallback if issue_number available
        if not issue_number:
            # No fallback possible, return None (CLI will handle with hint)
            return None

        logger.bind(
            domain="resolver",
            action="resolve",
            branch=branch,
            remote=remote,
        ).warning("Local read returned None, falling back to remote")

        return self._read_remote(branch, issue_number)

    def _read_local(self, branch: str) -> FlowStatusResponse | None:
        """Read from local SQLite only.

        Args:
            branch: Branch name

        Returns:
            FlowStatusResponse with LOCAL_SQLITE data_source, or None if not found
        """
        response = self.flow_service.get_flow_status(branch)
        if response is None:
            return None

        response.data_source = DataSource.LOCAL_SQLITE
        return response

    def _read_remote(self, branch: str, issue_number: int) -> FlowStatusResponse:
        """Read complete remote state from GitHub.

        Fetches issue body projection AND timeline from comments.

        Args:
            branch: Branch name
            issue_number: Issue number (required)

        Returns:
            FlowStatusResponse with ISSUE_BODY_FALLBACK data_source and timeline

        Raises:
            ValueError: If issue_number is None
            SystemError: If GitHub API fails
        """
        if issue_number is None:
            raise ValueError("issue_number required for remote source")

        from vibe3.clients import GitHubClient
        from vibe3.services.timeline_parser import parse_timeline_from_comments

        github_client = GitHubClient()

        logger.bind(
            domain="flow",
            action="resolve_remote",
            branch=branch,
            issue_number=issue_number,
        ).debug("Reading complete remote state from GitHub")

        # Fetch issue with comments
        issue_data = github_client.view_issue(issue_number, fields=["body", "comments"])
        if not issue_data or issue_data == "network_error":
            from vibe3.exceptions import SystemError

            raise SystemError(
                f"Failed to fetch issue #{issue_number}. "
                "GitHub API returned None or network error."
            )

        # Type guard: issue_data is dict at this point
        if not isinstance(issue_data, dict):
            from vibe3.exceptions import SystemError

            raise SystemError(
                f"Unexpected issue data type for #{issue_number}: {type(issue_data)}"
            )

        # Parse body for projection
        body = str(issue_data.get("body") or "")
        projection = parse_projection(body)

        # Parse timeline from comments
        comments = issue_data.get("comments") or []
        if not isinstance(comments, list):
            comments = []
        timeline = parse_timeline_from_comments(comments)

        # Build response with timeline
        blocked_reason_val = projection.blocked_reason
        blocked_summary = (
            compute_blocked_reason_summary(blocked_reason_val)
            if blocked_reason_val
            else None
        )
        return FlowStatusResponse(
            branch=branch,
            flow_slug=branch.replace("/", "-"),
            flow_status=projection.state,  # type: ignore[arg-type]
            blocked_by_issue=(
                projection.blocked_by[0] if projection.blocked_by else None
            ),
            blocked_reason=blocked_reason_val,
            blocked_reason_summary=blocked_summary,
            timeline=timeline,  # NEW: timeline from comments
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )
