"""Protocol definitions for Orchestra layer dependency injection.

These protocols define the interfaces required by GlobalDispatchCoordinator,
allowing it to depend on abstractions rather than concrete service implementations.
This breaks the orchestra→services/execution/roles circular dependency chain.

Note: Most protocols have been migrated to domain layer (dispatch_protocols.py).
The definitions below are maintained for backward compatibility during migration.
"""

from typing import Protocol

from vibe3.clients.git_client import GitClient

# Re-export protocols from domain for backward compatibility
from vibe3.domain.protocols.dispatch_protocols import (
    CapacityServiceProtocol,
    CheckServiceProtocol,
    FlowServiceProtocol,
    LabelDispatchCallable,
)
from vibe3.models import IssueInfo

__all__ = [
    "CapacityServiceProtocol",
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "LabelDispatchCallable",
    "IssueCollectionServiceProtocol",
    "FlowManagerProtocol",
]


class IssueCollectionServiceProtocol(Protocol):
    """Protocol for issue collection service operations."""

    def collect_open_issues(self, limit: int = 100) -> list[IssueInfo]:
        """Collect open GitHub issues.

        Args:
            limit: Maximum number of issues to collect

        Returns:
            List of normalized IssueInfo objects
        """
        ...


class FlowManagerProtocol(Protocol):
    """Protocol for flow manager operations (external consumer interface).

    This protocol exposes only the methods used by external consumers,
    not the internal service dependencies of FlowManager.
    """

    git: GitClient

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            Flow dict if found, None otherwise
        """
        ...

    def create_flow_for_issue(self, issue: IssueInfo) -> dict | None:
        """Create or reuse a flow for an issue.

        Args:
            issue: IssueInfo object

        Returns:
            Flow dict if created/reused, None on failure
        """
        ...
