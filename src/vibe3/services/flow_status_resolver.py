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

    def __init__(self, store: SQLiteClient) -> None:
        """Initialize resolver with SQLite client.

        Args:
            store: SQLiteClient for database operations
        """
        self.store = store
        self.flow_service = FlowService(store=store)

    def resolve(
        self,
        branch: str,
        source: Literal["local", "remote", "auto"],
        issue_number: int | None = None,
    ) -> FlowStatusResponse:
        """Resolve flow status with source strategy.

        Args:
            branch: Branch name to query
            source: "local" | "remote" | "auto"
            issue_number: Task issue number (required for remote fallback)

        Returns:
            FlowStatusResponse with data_source field set

        Raises:
            ValueError: If remote needed but no issue_number
            UserError: If local and flow not found
        """
        if source == "local":
            return self._read_local(branch)

        if source == "remote":
            if not issue_number:
                raise ValueError("issue_number required for remote source")
            return self._read_remote(branch, issue_number)

        # auto: local-first with remote fallback
        try:
            return self._read_local(branch)
        except Exception as e:
            logger.bind(
                domain="resolver",
                action="resolve",
                branch=branch,
                source=source,
                error=str(e),
            ).warning("Local read failed, falling back to remote")

            if not issue_number:
                raise ValueError(
                    "issue_number required for auto fallback when local fails"
                )

            return self._read_remote(branch, issue_number)

    def _read_local(self, branch: str) -> FlowStatusResponse:
        """Read from local SQLite only.

        Args:
            branch: Branch name

        Returns:
            FlowStatusResponse with LOCAL_SQLITE data_source

        Raises:
            UserError: If flow not found
        """
        response = self.flow_service.get_flow_status(branch)
        if response is None:
            from vibe3.exceptions import UserError

            raise UserError(f"Flow not found for branch '{branch}'")

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
            raise ValueError(f"Issue body is empty for issue #{issue_number}")

        projection = parse_projection_with_fallback(body)

        # Build minimal response from projection
        # Note: blocked state migrated to active by validator
        return FlowStatusResponse(
            branch=branch,
            flow_slug=branch.replace("/", "-"),
            flow_status=projection.state,  # type: ignore[arg-type]
            blocked_by_issue=(
                projection.blocked_by[0] if projection.blocked_by else None
            ),
            blocked_reason=projection.blocked_reason,
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )
