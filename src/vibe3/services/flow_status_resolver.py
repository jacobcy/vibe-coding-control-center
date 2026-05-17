"""FlowStatusResolver service - source-aware flow status reads."""

from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_body_service import parse_projection_with_fallback

if TYPE_CHECKING:
    pass


class FlowStatusResolver:
    """Resolver for source-aware flow status reads.

    Implements three strategies:
    - local: Read from SQLite only (no fallback, error if missing)
    - remote: Read from GitHub API + issue body projection (no SQLite)
    - auto: Local-first with remote fallback (try SQLite → fallback to issue body)
    """

    flow_service: FlowService
    github_client: GitHubClient

    def __init__(
        self,
        flow_service: FlowService | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        """Initialize resolver with service dependencies.

        Args:
            flow_service: FlowService for local reads
            github_client: GitHubClient for remote reads
        """
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()

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
        elif source == "remote":
            return self._read_remote(branch, issue_number)
        elif source == "auto":
            return self._read_auto(branch, issue_number)
        else:
            raise ValueError(f"Invalid source: {source}")

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
            raise UserError(f"Flow not found for branch '{branch}'")

        response.data_source = DataSource.LOCAL_SQLITE
        return response

    def _read_remote(self, branch: str, issue_number: int | None) -> FlowStatusResponse:
        """Read from GitHub issue body projection.

        Args:
            branch: Branch name
            issue_number: Issue number (required)

        Returns:
            FlowStatusResponse with ISSUE_BODY_FALLBACK data_source

        Raises:
            ValueError: If issue_number is None
        """
        if issue_number is None:
            raise ValueError("issue_number required for remote source")

        logger.bind(
            domain="flow",
            action="resolve_remote",
            branch=branch,
            issue_number=issue_number,
        ).debug("Reading flow status from issue body")

        body = self.github_client.get_issue_body(issue_number)
        projection = parse_projection_with_fallback(body)

        # Map projection.state to valid FlowStatusResponse.flow_status
        # Note: "blocked" not valid flow_status, inferred from blocked_by_issue
        flow_status: Literal["active", "done", "stale", "aborted"]
        if projection.state == "blocked":
            flow_status = "active"  # Blocked status inferred from blocked_by_issue
        elif projection.state in ("active", "done", "aborted"):
            flow_status = projection.state
        else:
            flow_status = "active"  # Default fallback

        # Build minimal response from projection
        return FlowStatusResponse(
            branch=branch,
            flow_slug=f"issue-{issue_number}",  # Synthetic slug
            flow_status=flow_status,
            blocked_by_issue=(
                projection.blocked_by[0] if projection.blocked_by else None
            ),
            blocked_reason=projection.blocked_reason,
            task_issue_number=issue_number,
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )

    def _read_auto(self, branch: str, issue_number: int | None) -> FlowStatusResponse:
        """Local-first with remote fallback.

        Args:
            branch: Branch name
            issue_number: Issue number (required for fallback)

        Returns:
            FlowStatusResponse from local or remote

        Raises:
            ValueError: If fallback needed but no issue_number
        """
        try:
            return self._read_local(branch)
        except UserError as e:
            logger.bind(
                domain="flow",
                action="resolve_auto",
                branch=branch,
            ).warning(f"Local read failed, attempting fallback: {e}")

            if issue_number is None:
                raise ValueError("issue_number required for auto fallback")

            return self._read_remote(branch, issue_number)
