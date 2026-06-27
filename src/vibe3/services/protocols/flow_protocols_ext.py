"""Extended protocol definitions for flow services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.config import TimelineCommentPolicy
    from vibe3.models import FlowStatusResponse


class FlowTimelineProtocol(Protocol):
    """Protocol for flow timeline event recording.

    Breaks the circular dependency between issue and flow subpackages.
    """

    def record_timeline_event(
        self,
        branch: str,
        event_type: str,
        actor: str,
        detail: str = "",
        issue_number: int | None = None,
        repo: str | None = None,
        policy: "TimelineCommentPolicy | None" = None,
    ) -> None:
        """Record a timeline event for a flow branch.

        Args:
            branch: Flow branch
            event_type: Event type identifier
            actor: Actor performing the action
            detail: Event detail/reason
            issue_number: GitHub issue number (optional)
            repo: Repository name (optional)
            policy: Timeline comment policy (optional)
        """
        ...


class FlowQueryProtocol(Protocol):
    """Protocol for flow query operations needed by task services.

    This breaks the circular dependency between task and flow subpackages.
    """

    @property
    def store(self) -> "SQLiteClient":
        """SQLite client for data access."""
        ...

    def get_flow_status(self, branch: str) -> "FlowStatusResponse | None":
        """Get flow status for a branch.

        Args:
            branch: Branch name to query

        Returns:
            Flow status or None if not found
        """
        ...

    def get_flow_for_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Get flow data for an issue.

        Args:
            issue_number: Issue number to query

        Returns:
            Flow data dict or None if not found
        """
        ...

    def list_flows(
        self,
        status: (
            "Literal['active', 'blocked', 'done', 'stale', 'review',"
            " 'failed', 'aborted'] | None"
        ) = None,
        *,
        statuses: list[str] | None = None,
    ) -> list["FlowStatusResponse"]:
        """List all flows, optionally filtered by status.

        Args:
            status: Optional status filter (e.g., "active", "done", "blocked", "stale",
                "review", "failed", "aborted")

        Returns:
            List of flow status responses
        """
        ...

    def block_flow(
        self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
        repo: str | None = None,
    ) -> None:
        """Mark a flow as blocked.

        Args:
            branch: Branch name
            reason: Blocking reason
            blocked_by_issue: Dependency issue number
            actor: Actor performing the block
            repo: Repository name
        """
        ...
