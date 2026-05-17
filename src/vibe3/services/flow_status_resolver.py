"""FlowStatusResolver service - source-aware flow status reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_body_service import parse_projection_with_fallback

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


SourceStrategy = Literal["local", "remote", "auto"]


class FlowStatusResolver:
    """Resolver for source-aware flow status reads.

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
            flow_service: Optional FlowService instance (defaults to creating one)
        """
        self.store = store
        self.flow_service = flow_service or FlowService(store=store)

    def resolve(
        self,
        branch: str,
        source: Literal["local", "remote", "auto"],
        issue_number: int | None = None,
    ) -> FlowStatusResponse | None:
        """Resolve flow status with source strategy.

        Args:
            branch: Branch name to query
            source: "local" | "remote" | "auto"
            issue_number: Task issue number (required for remote fallback)

        Returns:
            FlowStatusResponse with data_source field set,
            or None if auto mode and not found

        Raises:
            ValueError: If remote source but no issue_number
            UserError: If local source and flow not found
        """
        if source == "local":
            result = self._read_local(branch)
            if result is None:
                from vibe3.exceptions import UserError

                raise UserError(f"Flow not found for branch '{branch}'")
            return result

        if source == "remote":
            if not issue_number:
                from vibe3.exceptions import UserError

                raise UserError(
                    "Cannot use --source remote without issue number. "
                    "Bind a task issue first: vibe3 flow bind <issue> --role task"
                )
            return self._read_remote(branch, issue_number)

        # auto: local-first with remote fallback
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
            source=source,
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
        """Read from GitHub issue body projection.

        Args:
            branch: Branch name
            issue_number: Issue number (required)

        Returns:
            FlowStatusResponse with ISSUE_BODY_FALLBACK data_source

        Raises:
            ValueError: If issue_number is None or body is empty
        """
        if issue_number is None:
            raise ValueError("issue_number required for remote source")

        from vibe3.clients.github_client import GitHubClient

        github_client = GitHubClient()

        logger.bind(
            domain="flow",
            action="resolve_remote",
            branch=branch,
            issue_number=issue_number,
        ).debug("Reading flow status from issue body")

        body = github_client.get_issue_body(issue_number)
        if not body:
            from vibe3.exceptions import SystemError

            raise SystemError(
                f"Failed to fetch issue body for #{issue_number}. "
                "GitHub API returned empty or None."
            )

        projection = parse_projection_with_fallback(body)

        # Directly use projection state (no normalization)
        # Blocked state is inferred from projection's blocked_by/blocked_reason fields
        # Remote sync semantics: respect the actual state from issue body projection
        response_state = projection.state

        # Build minimal response from projection
        return FlowStatusResponse(
            branch=branch,
            flow_slug=branch.replace("/", "-"),
            flow_status=response_state,  # type: ignore[arg-type]
            blocked_by_issue=(
                projection.blocked_by[0] if projection.blocked_by else None
            ),
            blocked_reason=projection.blocked_reason,
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )
