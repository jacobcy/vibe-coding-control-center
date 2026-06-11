"""Extended protocol definitions for flow services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from vibe3.models import FlowStatusResponse


class FlowQueryProtocol(Protocol):
    """Protocol for flow query operations needed by task services.

    This breaks the circular dependency between task and flow subpackages.
    """

    def get_flow_status(self, branch: str) -> FlowStatusResponse | None:
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
