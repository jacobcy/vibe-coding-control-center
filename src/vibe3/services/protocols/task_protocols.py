"""Protocol definitions for task services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vibe3.models import FlowStatusResponse


class TaskQueryProtocol(Protocol):
    """Protocol for task query operations needed by flow services.

    This breaks the circular dependency between flow and task subpackages.
    """

    def get_task_for_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Get task data for an issue.

        Args:
            issue_number: Issue number to query

        Returns:
            Task data dict or None if not found
        """
        ...

    def has_task_issue(self, flow_status: FlowStatusResponse | None) -> bool:
        """Check if flow status has a bound task issue.

        Args:
            flow_status: Flow status to check

        Returns:
            True if task issue is bound
        """
        ...

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: str,
        actor: str | None = None,
    ) -> None:
        """Link an issue to a flow.

        Args:
            branch: Branch name
            issue_number: Issue number to link
            role: Role of the issue (e.g., "dependency")
            actor: Actor performing the link
        """
        ...
